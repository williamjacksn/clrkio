import datetime
import flask
import logging
import os
import pathlib
import requests
import sqlite3

from typing import Dict, List

log = logging.getLogger(__name__)
app = flask.Flask(__name__)


def api_ts_to_date(api_timestamp):
    if api_timestamp is None:
        rv = None
    else:
        rv = datetime.date(1970, 1, 1) + datetime.timedelta(seconds=api_timestamp / 1000)
        if rv.year == 1:
            log.warning('The timestamp {!r} converted to {!r}, which is invalid'.format(api_timestamp, rv))
            rv = None
    return rv


def convert_member_id(m):
    if m is None:
        rv = None
    else:
        rv = m[:3] + '-' + m[5:9] + '-' + m[9:]
    return rv


def to_db(d):
    if d is None:
        rv = None
    elif isinstance(d, bool):
        rv = int(d)
    elif isinstance(d, (str, int, float)):
        rv = d
    elif isinstance(d, datetime.date):
        rv = str(d)
    else:
        log.warning('I do not know how to convert {!r} for the database'.format(d))
        rv = None
    return rv


class Household(object):
    allowed_data_keys = {'children', 'coupleName', 'desc1', 'desc2', 'desc3',
                         'emailAddress', 'headOfHouse',
                         'headOfHouseIndividualId', 'householdName',
                         'includeLatLong', 'latitude', 'longitude', 'phone',
                         'postalCode', 'spouse', 'state'}
    required_data_keys = {'coupleName', 'desc1', 'headOfHouse', 'householdName',
                          'includeLatLong', 'state'}
    allowed_indiv_keys = {'email', 'fullName', 'givenName', 'individualId',
                          'memberId', 'phone', 'preferredName', 'surname'}
    required_indiv_keys = {'fullName', 'givenName', 'individualId',
                           'preferredName'}

    def __init__(self, data):
        h_keys = set(data.keys())
        if not self.required_data_keys.issubset(h_keys):
            missing_keys = self.required_data_keys.difference(h_keys)
            err = ('While processing household {!r}, I did not find one or '
                   'more data keys that I expected to find: {}')
            log.warning(err.format(data.get('householdName'), missing_keys))
        if not h_keys.issubset(self.allowed_data_keys):
            extra_keys = h_keys.difference(self.allowed_data_keys)
            err = ('While processing household {!r}, I found one or more data '
                   'keys that I did not expect to find: {}')
            log.warning(err.format(data.get('householdName'), extra_keys))
        self.children = data.get('children')
        self.couple_name = data.get('coupleName')
        self.description_1 = data.get('desc1')
        self.description_2 = data.get('desc2')
        self.description_3 = data.get('desc3')
        self.email_address = data.get('emailAddress')
        self.head_of_house = self._parse_individual(data.get('headOfHouse', {}))
        self.hoh_id = data.get('headOfHouseIndividualId')
        self.household_name = data.get('householdName')
        self.include_lat_long = data.get('includeLatLong')
        self.latitude = data.get('latitude')
        self.longitude = data.get('longitude')
        self.phone = data.get('phone')
        if 'spouse' in data:
            self.spouse = self._parse_individual(data.get('spouse', {}))
            self.spouse_id = self.spouse.get('individual_id')
        else:
            self.spouse = None
            self.spouse_id = None
        self.state = data.get('state')
        self.children = []
        for child in data.get('children', []):
            self.children.append(self._parse_individual(child))

    @staticmethod
    def disable_all():
        query_db('UPDATE households SET enabled = 0')

    @staticmethod
    def get_by_hoh_id(hoh_id):
        sql = 'SELECT * FROM households WHERE head_of_house = ?'
        return query_db(sql, args=(hoh_id,), one=True)

    @staticmethod
    def prune_disabled():
        query_db('DELETE FROM households WHERE enabled = 0')

    def insert(self):
        sql = ('INSERT INTO households (couple_name, description_1, '
               'description_2, description_3, email_address, enabled, '
               'head_of_house, household_name, include_lat_long, latitude, '
               'longitude, phone, spouse, state) VALUES (?, ?, ?, ?, ?, 1, ?, '
               '?, ?, ?, ?, ?, ?, ?)')
        t = (self.couple_name, self.description_1, self.description_2,
             self.description_3, self.email_address,
             self.hoh_id, self.household_name, self.include_lat_long,
             self.latitude, self.longitude, self.phone, self.spouse_id,
             self.state)
        args = tuple(map(to_db, t))
        query_db(sql, args=args)
        self._refresh_children()
        self._update_individual_details()

    def update(self):
        sql = ('UPDATE households SET couple_name = ?, description_1 = ?, '
               'description_2 = ?, description_3 = ?, email_address = ?, '
               'enabled = 1, household_name = ?, include_lat_long = ?, '
               'latitude = ?, longitude = ?, phone = ?, spouse = ?, state = ? '
               'WHERE head_of_house = ?')
        t = (self.couple_name, self.description_1, self.description_2,
             self.description_3, self.email_address, self.household_name,
             self.include_lat_long, self.latitude, self.longitude, self.phone,
             self.spouse_id, self.state, self.hoh_id)
        args = tuple(map(to_db, t))
        query_db(sql, args=args)
        self._refresh_children()
        self._update_individual_details()

    @classmethod
    def _parse_individual(cls, data):
        d_keys = set(data.keys())
        if not cls.required_indiv_keys.issubset(d_keys):
            missing_keys = cls.required_indiv_keys.difference(d_keys)
            err = ('While processing member of household {!r}, I did not find '
                   'one or more data keys that I expected to find: {}')
            log.warning(err.format(data.get('fullName'), missing_keys))
        if not d_keys.issubset(cls.allowed_indiv_keys):
            extra_keys = d_keys.difference(cls.allowed_indiv_keys)
            err = ('While processing member of household {!r}, I found one or '
                   'more data keys that I did not expect to find: {}')
            log.warning(err.format(data.get('fullName'), extra_keys))
        individual = {
            'email': data.get('email'), 'full_name': data.get('fullName'),
            'given_name': data.get('givenName'),
            'individual_id': data.get('individualId'),
            'member_id': data.get('memberId'), 'phone': data.get('phone'),
            'preferred_name': data.get('preferredName'),
            'surname': data.get('surname')}
        return individual

    def _refresh_children(self):
        sql = 'DELETE FROM household_children WHERE head_of_house = ?'
        query_db(sql, args=(self.hoh_id,))
        sql = ('INSERT INTO household_children (head_of_house, child) VALUES '
               '(?, ?)')
        for child in self.children:
            args = (self.hoh_id, child.get('individual_id'))
            query_db(sql, args=args)

    def _update_individual_details(self):
        sql = ('UPDATE members SET email = ?, given_name = ?, phone = ?, '
               'preferred_name = ?, surname = ? WHERE individual_id = ?')
        hoh = self.head_of_house
        args = (hoh.get('email'), hoh.get('given_name'), hoh.get('phone'),
                hoh.get('preferred_name'), hoh.get('surname'),
                hoh.get('individual_id'))
        query_db(sql, args=args)
        if self.spouse is not None:
            sp = self.spouse
            args = (sp.get('email'), sp.get('given_name'), sp.get('phone'),
                    sp.get('preferred_name'), sp.get('surname'),
                    sp.get('individual_id'))
            query_db(sql, args=args)
        for ch in self.children:
            args = (ch.get('email'), ch.get('given_name'), ch.get('phone'),
                    ch.get('preferred_name'), ch.get('surname'),
                    ch.get('individual_id'))
            query_db(sql, args=args)


class Member(object):
    allowed_data_keys = {'baptismDate', 'baptismRatified', 'birthCountry', 'birthPlace', 'birthdate', 'bornInCovenant',
                         'confirmationDate', 'confirmationRatified', 'endowmentDate', 'endowmentRatified',
                         'endowmentTemple', 'fathersBirthDate', 'fathersName', 'fromAddressUnknown', 'fullName',
                         'gender', 'individualId', 'isSpouseMember', 'maidenName', 'marriageDate', 'marriagePlace',
                         'memberId', 'missionCountry', 'missionLanguage', 'mothersBirthDate', 'mothersName',
                         'movedInDate', 'notAccountable', 'priesthoodOffices', 'priorUnit', 'priorUnitMoveDate',
                         'priorUnitName', 'recommendExpirationDate', 'recommendStatus', 'sealedParentsDate',
                         'sealedSpouseDate', 'sealedSpouseTemple', 'sealedToParentsTemple', 'sealingToParentsRatified',
                         'sealingToSpouseRatified', 'spouseBirthDate', 'spouseDeceased', 'spouseMember',
                         'spouseMemberId', 'spouseName'}
    required_data_keys = {'birthdate', 'fromAddressUnknown', 'fullName', 'gender', 'individualId'}
    allowed_po_keys = {'ordinationDate', 'performedBy', 'performedByMrn', 'priesthoodOfficeCode', 'ratified'}
    required_po_keys = {'ordinationDate', 'performedBy', 'priesthoodOfficeCode', 'ratified'}

    def __init__(self, data):
        m_keys = set(data.keys())
        if not self.required_data_keys.issubset(m_keys):
            missing_keys = self.required_data_keys.difference(m_keys)
            err = 'While processing member {!r}, I did not find one or more data keys that I expected to find: {}'
            log.warning(err.format(data.get('fullName'), missing_keys))
        if not m_keys.issubset(self.allowed_data_keys):
            extra_keys = m_keys.difference(self.allowed_data_keys)
            err = 'While processing member {!r}, I found one or more data keys that I did not expect to find: {}'
            log.warning(err.format(data.get('fullName'), extra_keys))
        self.baptism_date = api_ts_to_date(data.get('baptismDate'))
        self.baptism_ratified = data.get('baptismRatified')
        self.birth_country = data.get('birthCountry')
        self.birth_place = data.get('birthPlace')
        self.birthdate = api_ts_to_date(data.get('birthdate'))
        self.born_in_covenant = data.get('bornInCovenant')
        self.confirmation_date = api_ts_to_date(data.get('confirmationDate'))
        self.confirmation_ratified = data.get('confirmationRatified')
        self.email = None
        self.enabled = True
        self.endowment_date = api_ts_to_date(data.get('endowmentDate'))
        self.endowment_ratified = data.get('endowmentRatified')
        self.endowment_temple = data.get('endowmentTemple')
        self.fathers_birth_date = api_ts_to_date(data.get('fathersBirthDate'))
        self.fathers_name = data.get('fathersName')
        self.from_address_unknown = data.get('fromAddressUnknown')
        self.full_name = data.get('fullName')
        self.gender = data.get('gender')
        self.given_name = None
        self.individual_id = data.get('individualId')
        self.is_spouse_member = data.get('isSpouseMember')
        self.maiden_name = data.get('maidenName')
        self.marriage_date = api_ts_to_date(data.get('marriageDate'))
        self.marriage_place = data.get('marriagePlace')
        self.member_id = convert_member_id(data.get('memberId'))
        self.mission_country = data.get('missionCountry')
        self.mission_language = data.get('missionLanguage')
        self.mothers_birth_date = api_ts_to_date(data.get('mothersBirthDate'))
        self.mothers_name = data.get('mothersName')
        self.moved_in_date = api_ts_to_date(data.get('movedInDate'))
        self.not_accountable = data.get('notAccountable')
        self.phone = None
        self.preferred_name = None
        self.prior_unit = data.get('priorUnit')
        self.prior_unit_move_date = api_ts_to_date(
            data.get('priorUnitMoveDate'))
        self.prior_unit_name = data.get('priorUnitName')
        self.recommend_expiration_date = api_ts_to_date(
            data.get('recommendExpirationDate'))
        self.recommend_status = data.get('recommendStatus')
        self.sealed_parents_date = api_ts_to_date(data.get('sealedParentsDate'))
        self.sealed_spouse_date = api_ts_to_date(data.get('sealedSpouseDate'))
        self.sealed_spouse_temple = data.get('sealedSpouseTemple')
        self.sealed_to_parents_temple = data.get('sealedToParentsTemple')
        self.sealing_to_parents_ratified = data.get('sealingToParentsRatified')
        self.sealing_to_spouse_ratified = data.get('sealingToSpouseRatified')
        self.spouse_birth_date = api_ts_to_date(data.get('spouseBirthDate'))
        self.spouse_deceased = data.get('spouseDeceased')
        self.spouse_member = data.get('spouseMember')
        self.spouse_member_id = convert_member_id(data.get('spouseMemberId'))
        self.spouse_name = data.get('spouseName')
        self.surname = None

        self.priesthood_offices = []  # type: List[Dict]
        for po in data.get('priesthoodOffices', []):
            po_keys = set(po.keys())
            if not self.required_po_keys.issubset(po_keys):
                missing_keys = self.required_po_keys.difference(po_keys)
                err = ('While processing member {!r}, I did not find one or '
                       'more priesthood office data keys that I expected to '
                       'find: {}')
                log.warning(err.format(data.get('fullName'), missing_keys))
            if not po_keys.issubset(self.allowed_po_keys):
                extra_keys = po_keys.difference(self.allowed_po_keys)
                err = ('While processing member {!r}, I found one or more '
                       'priesthood office data keys that I did not expect to '
                       'find: {}')
                log.warning(err.format(data.get('fullName'), extra_keys))
            office = {
                'ordination_date': api_ts_to_date(po.get('ordinationDate')),
                'performed_by': po.get('performedBy'),
                'performed_by_mrn': convert_member_id(po.get('performedByMrn')),
                'priesthood_office_code': po.get('priesthoodOfficeCode'),
                'ratified': po.get('ratified')}
            self.priesthood_offices.append(office)

    @staticmethod
    def get_by_id(individual_id):
        sql = 'SELECT * FROM members WHERE individual_id = ?'
        return query_db(sql, args=(individual_id,), one=True)

    @staticmethod
    def get_all_enabled():
        sql = 'SELECT * FROM members WHERE enabled = 1'
        return query_db(sql)

    @staticmethod
    def get_all_disabled():
        sql = 'SELECT * FROM members WHERE enabled = 0'
        return query_db(sql)

    @staticmethod
    def disable_all():
        query_db('UPDATE members SET enabled = 0')

    @staticmethod
    def prune_disabled():
        query_db('DELETE FROM members WHERE enabled = 0')

    def insert(self):
        log.debug('Inserting {!r} into the database'.format(self.full_name))
        sql = ('INSERT INTO members (baptism_date, baptism_ratified, '
               'birth_country, birth_place, birthdate, born_in_covenant, '
               'confirmation_date, confirmation_ratified, email, enabled, '
               'endowment_date, endowment_ratified, endowment_temple, '
               'fathers_birth_date, fathers_name, from_address_unknown, '
               'full_name, gender, given_name, individual_id, '
               'is_spouse_member, maiden_name, marriage_date, marriage_place, '
               'member_id, mission_country, mission_language, '
               'mothers_birth_date, mothers_name, moved_in_date, '
               'not_accountable, phone, preferred_name, prior_unit, '
               'prior_unit_move_date, prior_unit_name, '
               'recommend_expiration_date, recommend_status, '
               'sealed_parents_date, sealed_spouse_date, sealed_spouse_temple, '
               'sealed_to_parents_temple, sealing_to_parents_ratified, '
               'sealing_to_spouse_ratified, spouse_birth_date, '
               'spouse_deceased, spouse_member, spouse_member_id, spouse_name, '
               'surname) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, '
               '?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '
               '?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
        t = (self.baptism_date, self.baptism_ratified, self.birth_country,
             self.birth_place, self.birthdate, self.born_in_covenant,
             self.confirmation_date, self.confirmation_ratified, self.email,
             self.endowment_date, self.endowment_ratified,
             self.endowment_temple, self.fathers_birth_date, self.fathers_name,
             self.from_address_unknown, self.full_name, self.gender,
             self.given_name, self.individual_id, self.is_spouse_member,
             self.maiden_name, self.marriage_date, self.marriage_place,
             self.member_id, self.mission_country, self.mission_language,
             self.mothers_birth_date, self.mothers_name, self.moved_in_date,
             self.not_accountable, self.phone, self.preferred_name,
             self.prior_unit, self.prior_unit_move_date, self.prior_unit_name,
             self.recommend_expiration_date, self.recommend_status,
             self.sealed_parents_date, self.sealed_spouse_date,
             self.sealed_spouse_temple, self.sealed_to_parents_temple,
             self.sealing_to_parents_ratified, self.sealing_to_spouse_ratified,
             self.spouse_birth_date, self.spouse_deceased, self.spouse_member,
             self.spouse_member_id, self.spouse_name, self.surname)
        args = tuple(map(to_db, t))
        query_db(sql, args=args)
        self._refresh_priesthood_offices()

    def update(self):
        sql = ('UPDATE members SET baptism_date = ?, baptism_ratified = ?, '
               'birth_country = ?, birth_place = ?, birthdate = ?, '
               'born_in_covenant = ?, confirmation_date = ?, '
               'confirmation_ratified = ?, email = ?, enabled = 1, '
               'endowment_date = ?, endowment_ratified = ?, '
               'endowment_temple = ?, fathers_birth_date = ?, '
               'fathers_name = ?, from_address_unknown = ?, full_name = ?, '
               'gender = ?, given_name = ?, is_spouse_member = ?, '
               'maiden_name = ?, marriage_date = ?, marriage_place = ?, '
               'member_id = ?, mission_country = ?, mission_language = ?, '
               'mothers_birth_date = ?, mothers_name = ?, moved_in_date = ?, '
               'not_accountable = ?, phone = ?, preferred_name = ?, '
               'prior_unit = ?, prior_unit_move_date = ?, prior_unit_name = ?, '
               'recommend_expiration_date = ?, recommend_status = ?, '
               'sealed_parents_date = ?, sealed_spouse_date = ?, '
               'sealed_spouse_temple = ?, sealed_to_parents_temple = ?, '
               'sealing_to_parents_ratified = ?, '
               'sealing_to_spouse_ratified = ?, spouse_birth_date = ?, '
               'spouse_deceased = ?, spouse_member = ?, spouse_member_id = ?, '
               'spouse_name = ?, surname = ? WHERE individual_id = ?')
        t = (self.baptism_date, self.baptism_ratified, self.birth_country,
             self.birth_place, self.birthdate, self.born_in_covenant,
             self.confirmation_date, self.confirmation_ratified, self.email,
             self.endowment_date, self.endowment_ratified,
             self.endowment_temple, self.fathers_birth_date, self.fathers_name,
             self.from_address_unknown, self.full_name, self.gender,
             self.given_name, self.is_spouse_member, self.maiden_name,
             self.marriage_date, self.marriage_place, self.member_id,
             self.mission_country, self.mission_language,
             self.mothers_birth_date, self.mothers_name, self.moved_in_date,
             self.not_accountable, self.phone, self.preferred_name,
             self.prior_unit, self.prior_unit_move_date, self.prior_unit_name,
             self.recommend_expiration_date, self.recommend_status,
             self.sealed_parents_date, self.sealed_spouse_date,
             self.sealed_spouse_temple, self.sealed_to_parents_temple,
             self.sealing_to_parents_ratified, self.sealing_to_spouse_ratified,
             self.spouse_birth_date, self.spouse_deceased, self.spouse_member,
             self.spouse_member_id, self.spouse_name, self.surname,
             self.individual_id)
        args = tuple(map(to_db, t))
        query_db(sql, args=args)
        self._refresh_priesthood_offices()

    def delete(self):
        sql = 'DELETE FROM members WHERE individual_id = ?'
        query_db(sql, args=(self.individual_id,))

    def _refresh_priesthood_offices(self):
        sql = 'DELETE FROM priesthood_offices WHERE individual_id = ?'
        query_db(sql, args=(self.individual_id,))
        for po in self.priesthood_offices:
            sql = ('INSERT INTO priesthood_offices (individual_id, '
                   'ordination_date, performed_by, performed_by_mrn, '
                   'priesthood_office_code, ratified) VALUES (?, ?, ?, ?, ?, '
                   '?)')
            t = (self.individual_id, po['ordination_date'], po['performed_by'],
                 po['performed_by_mrn'], po['priesthood_office_code'],
                 po['ratified'])
            args = tuple(map(to_db, t))
            query_db(sql, args=args)


def get_conf_dir():
    conf_dir = pathlib.Path(os.environ.get('USERPROFILE')).resolve() / '.config/clrkio'
    if not conf_dir.exists():
        conf_dir.mkdir(parents=True)
    return conf_dir


def get_db_path():
    return get_conf_dir() / 'clrkio.sqlite'


def get_db():
    db = getattr(flask.g, '_database', None)
    if db is None:
        db = flask.g._database = sqlite3.connect(str(get_db_path()))
    db.isolation_level = None
    db.row_factory = sqlite3.Row
    return db


def query_db(query, args=None, one=False):
    if args is None:
        args = ()
    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


@app.before_first_request
def init_db():
    if get_db_path().exists():
        log.debug('The database at {} already exists'.format(get_db_path()))
        return
    log.debug('Initializing the database at {}'.format(get_db_path()))
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())


@app.teardown_appcontext
def close_connection(_):
    db = getattr(flask.g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    members = Member.get_all_enabled()
    return flask.render_template('index.html', members=members)


@app.route('/members/<int:individual_id>')
def member_detail(individual_id):
    member = Member.get_by_id(individual_id)
    return flask.render_template('member_detail.html', member=member)


@app.route('/pre_sync')
def pre_sync():
    return flask.render_template('pre_sync.html')


@app.route('/sync', methods=['POST'])
def sync():
    log.debug('Starting sync')
    s = requests.Session()
    data = {'username': flask.request.form['username'],
            'password': flask.request.form['password']}
    signin_url = 'https://signin.lds.org/login.html'
    log.debug('Attempting to sign in at ' + signin_url)
    s.post(signin_url, data=data)
    user_detail_url = ('https://www.lds.org/mobiledirectory/services/v2/'
                       'ldstools/current-user-detail')
    log.debug('Attempting to get current user details at ' + user_detail_url)
    user_detail_response = s.get(user_detail_url)
    user_detail = user_detail_response.json()
    home_unit_number = user_detail['homeUnitNbr']
    params = {'unitNumber': home_unit_number}
    records_url = ('https://www.lds.org/mls/mbr/services/report/'
                   'membership-records')
    log.debug('Attempting to get membership records from ' + records_url)
    s.headers['accept'] = 'application/json'
    r = s.get(records_url, params=params).json()
    log.debug(r)
    added = []
    Member.disable_all()
    for member in r:
        m = Member(member)
        db_m = Member.get_by_id(m.individual_id)
        if db_m is None:
            m.insert()
            added.append(m)
        else:
            m.update()
    removed = Member.get_all_disabled()
    Member.prune_disabled()

    hh_url = ('https://www.lds.org/mobiledirectory/services/v2/ldstools/'
              'member-detaillist-with-callings/' + str(home_unit_number))
    log.debug('Attempting to get household information from ' + hh_url)
    r = s.get(hh_url).json()
    Household.disable_all()
    for household in r['households']:
        h = Household(household)
        db_h = Household.get_by_hoh_id(h.hoh_id)
        if db_h is None:
            h.insert()
        else:
            h.update()
    Household.prune_disabled()
    log.debug('Sync done')

    return flask.render_template('sync.html', added=added, removed=removed)


def main():
    logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level='DEBUG')
    app.run(host='0.0.0.0', debug=True)

if __name__ == '__main__':
    main()
