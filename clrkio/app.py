import apscheduler.schedulers.background
import clrkio.church
import clrkio.db
import clrkio.settings
import collections
import datetime
import flask
import flask.logging
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

app = flask.Flask('clrkio')
app.wsgi_app = werkzeug.middleware.proxy_fix.ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_port=1)
log = logging.getLogger(__name__)

app.secret_key = settings.secret_key
app.config['PREFERRED_URL_SCHEME'] = settings.scheme
app.config['SERVER_NAME'] = settings.server_name

if settings.scheme == 'https':
    app.config['SESSION_COOKIE_SECURE'] = True


def permission_required(permission: str):
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            log.debug(f'Checking permission for {flask.g.email}')
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
    log.debug(f'{flask.request.method} {flask.request.path}')
    if settings.permanent_sessions:
        flask.session.permanent = True
    flask.g.settings = settings
    flask.g.email = flask.session.get('email')
    flask.g.db = clrkio.db.Database(settings)
    flask.g.permissions = flask.g.db.get_permissions(flask.g.email)


@app.route('/')
@permission_required('admin')
def index():
    return flask.render_template('index.html')


@app.route('/authorize')
def authorize():
    for key, value in flask.request.values.items():
        log.debug(f'{key}: {value}')
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
    claim = jwt.decode(id_token, options={'verify_signature': False}, algorithms=algorithms)
    flask.session['email'] = claim.get('email')
    target = flask.session.pop('sign-in-target-url', flask.url_for('index'))
    return flask.redirect(target)


@app.route('/health-check')
def health_check():
    db = clrkio.db.Database(settings)
    return f'clrkio version {settings.version} / schema version {db.version}'


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
            'name': member_data.get('displayName'),
            'birthday': datetime.date.fromisoformat(member_data.get('birthDate')),
            'email': member_data.get('email'),
            'phone': member_data.get('phone'),
            'age_group': member_data.get('ageGroup'),
            'gender': member_data.get('sex')
        })


def send_email(to: str, body: str):
    log.debug(f'Sending email to {to}')
    auth = ('api', settings.mailgun_api_key)
    data = {
        'from': settings.mailgun_sender,
        'to': to,
        'subject': 'Recent changes to membership records',
        'html': body
    }
    requests.post(f'https://api.mailgun.net/v3/{settings.mailgun_domain}/messages', auth=auth, data=data)


def sync():
    start = datetime.datetime.utcnow()
    log.info(f'Starting sync at {start}')
    ct = clrkio.church.ChurchToolsClient(settings)
    _data = ct.get_unit_members()
    db = clrkio.db.Database(settings)
    db.pre_sync_members()
    sync_results = []
    for h in _data.get('households'):
        if 'members' in h:
            for m in h.get('members'):
                sync_result = sync_one(m)
                if sync_result is not None:
                    sync_results.append(sync_result)
    sync_results.extend([{'result': 'removed', 'data': r} for r in db.post_sync_members()])
    end = datetime.datetime.utcnow()
    log.info(f'Ending sync at {end}, duration {end - start}')
    log.debug(sync_results)
    stats = collections.Counter([r.get('result') for r in sync_results])
    log.info(stats)
    if stats['added'] + stats['changed'] + stats['removed'] > 0:
        with app.app_context():
            sync_report = flask.render_template('email/sync-report.html', sync_time=start, sync_results=sync_results)
            for row in db.get_member_changes_recipients():
                send_email(row.get('email'), sync_report)


def main():
    logging.basicConfig(format=settings.log_format, level='DEBUG', stream=sys.stdout)
    log.debug(f'clrkio {settings.version}')
    if not settings.log_level == 'DEBUG':
        log.debug(f'Changing log level to {settings.log_level}')
    logging.getLogger().setLevel(settings.log_level)

    for logger, level in settings.other_log_levels.items():
        log.debug(f'Changing log level for {logger} to {level}')
        logging.getLogger(logger).setLevel(level)

    db = clrkio.db.Database(settings)
    if settings.reset_database:
        db.reset()

    db.migrate()
    db.bootstrap_admin()

    scheduler.start()
    if settings.auto_sync:
        scheduler.add_job(sync)
        scheduler.add_job(sync, 'interval', hours=24)

    waitress.serve(app, ident=None, port=settings.port, threads=settings.web_server_threads)
