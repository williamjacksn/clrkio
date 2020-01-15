import apscheduler.schedulers.background
import clrkio.church
import clrkio.db
import clrkio.settings
import collections
import datetime
import flask
import functools
import jwt
import logging
import requests
import sys
import urllib.parse
import uuid
import waitress
import werkzeug.middleware.proxy_fix


settings = clrkio.settings.Settings()
scheduler = apscheduler.schedulers.background.BackgroundScheduler()

app = flask.Flask(__name__)
app.wsgi_app = werkzeug.middleware.proxy_fix.ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_port=1)

app.secret_key = settings.secret_key
app.config['PREFERRED_URL_SCHEME'] = settings.scheme
app.config['SERVER_NAME'] = settings.server_name

if settings.scheme == 'https':
    app.config['SESSION_COOKIE_SECURE'] = True


def permission_required(permission: str):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            app.logger.debug(f'Checking permission for {flask.g.email}')
            if flask.g.email is None:
                flask.session['sign-in-target-url'] = flask.request.url
                return flask.redirect(flask.url_for('sign_in'))
            if permission in flask.g.permissions:
                return f(*args, **kwargs)
            flask.g.required_permission = permission
            return flask.render_template('not-authorized.html')

        return decorated_function

    return decorator


@app.before_request
def before_request():
    app.logger.debug(f'{flask.request.method} {flask.request.path}')
    if settings.permanent_sessions:
        flask.session.permanent = True
    flask.g.settings = settings
    flask.g.email = flask.session.get('email')
    flask.g.db = clrkio.db.Database(settings)
    flask.g.permissions = flask.g.db.get_permissions(flask.g.email)


@app.route('/')
@permission_required('admin')
def index():
    db: clrkio.db.Database = flask.g.db
    members = db.get_all_members()
    return flask.render_template('index.html', members=members)


@app.route('/authorize')
def authorize():
    for key, value in flask.request.values.items():
        app.logger.debug(f'{key}: {value}')
    if flask.session.get('state') != flask.request.values.get('state'):
        return 'State mismatch', 401
    discovery_document = requests.get(settings.openid_discovery_document).json()
    token_endpoint = discovery_document.get('token_endpoint')
    data = {
        'code': flask.request.values.get('code'),
        'client_id': settings.openid_client_id,
        'client_secret': settings.openid_client_secret,
        'redirect_uri': flask.url_for('authorize', _external=True),
        'grant_type': 'authorization_code'
    }
    resp = requests.post(token_endpoint, data=data).json()
    id_token = resp.get('id_token')
    algorithms = discovery_document.get('id_token_signing_alg_values_supported')
    claim = jwt.decode(id_token, verify=False, algorithms=algorithms)
    flask.session['email'] = claim.get('email')
    target = flask.session.pop('sign-in-target-url', flask.url_for('index'))
    return flask.redirect(target)


@app.route('/health-check')
def health_check():
    return 'ok'


@app.route('/sign-in')
def sign_in():
    state = str(uuid.uuid4())
    flask.session['state'] = state
    redirect_uri = flask.url_for('authorize', _external=True)
    query = {
        'client_id': settings.openid_client_id,
        'response_type': 'code',
        'scope': 'openid email profile',
        'redirect_uri': redirect_uri,
        'state': state
    }
    discovery_document = requests.get(settings.openid_discovery_document).json()
    auth_endpoint = discovery_document.get('authorization_endpoint')
    auth_url = f'{auth_endpoint}?{urllib.parse.urlencode(query)}'
    return flask.redirect(auth_url, 307)


@app.route('/sign-out')
def sign_out():
    flask.session.pop('email')
    return flask.redirect(flask.url_for('index'))


def sync_one(member_data):
    db = clrkio.db.Database(settings)
    individual_id = member_data.get('individualId', -1)
    if individual_id > 0:
        return db.sync_member({
            'individual_id': member_data.get('individualId'),
            'name': member_data.get('preferredName'),
            'birthday': datetime.date.fromisoformat(member_data.get('birthDay')),
            'email': member_data.get('email'),
            'age_group': member_data.get('ageGroup'),
            'gender': member_data.get('gender')
        })


def sync():
    start = datetime.datetime.utcnow()
    app.logger.info(f'Starting sync at {start}')
    ct = clrkio.church.ChurchToolsClient(settings)
    _data = ct.get_unit_members()
    db = clrkio.db.Database(settings)
    db.pre_sync_members()
    sync_results = []
    for h in _data.get('households'):
        sync_result = sync_one(h.get('headOfHouse'))
        if sync_result is not None:
            sync_results.append(sync_result)
        if 'spouse' in h:
            sync_result = sync_one(h.get('spouse'))
            if sync_result is not None:
                sync_results.append(sync_result)
        for ch in h.get('children', []):
            sync_results.append(sync_one(ch))
    sync_results.extend([{'result': 'removed', 'data': r} for r in db.post_sync_members()])
    end = datetime.datetime.utcnow()
    app.logger.info(f'Ending sync at {end}, duration {end - start}')
    app.logger.debug(sync_results)
    stats = collections.Counter([r.get('result') for r in sync_results])
    app.logger.info(stats)
    if stats['added'] + stats['changed'] + stats['removed'] > 0:
        with app.app_context():
            sync_report = flask.render_template('email/sync-report.jinja2', sync_time=start, sync_results=sync_results)
            app.logger.info(sync_report)


def main():
    logging.basicConfig(format=settings.log_format, level='DEBUG', stream=sys.stdout)
    app.logger.debug(f'clrkio {settings.version}')
    if not settings.log_level == 'DEBUG':
        app.logger.debug(f'Changing log level to {settings.log_level}')
    logging.getLogger().setLevel(settings.log_level)

    for logger, level in settings.other_log_levels.items():
        app.logger.debug(f'Changing log level for {logger} to {level}')
        logging.getLogger(logger).setLevel(level)

    db = clrkio.db.Database(settings)
    if settings.reset_database:
        db.reset()

    db.migrate()
    db.bootstrap_admin()

    scheduler.start()
    if settings.auto_sync:
        scheduler.add_job(sync)

    waitress.serve(app, ident=None, port=settings.port, threads=settings.web_server_threads)
