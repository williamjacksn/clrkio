import clrkio.settings
import datetime
import logging
import requests

log = logging.getLogger(__name__)


class ChurchToolsClient:
    def __init__(self, settings: clrkio.settings.Settings):
        self.settings = settings
        self.session = requests.session()

        # get access token

        token_url = 'https://ident.churchofjesuschrist.org/sso/oauth2/access_token'
        _data = {
            'client_id': self.settings.church_tools_client_id,
            'client_secret': self.settings.church_tools_client_secret,
            'grant_type': 'client_credentials',
            'scope': 'openid profile'
        }
        _response = self.session.post(token_url, data=_data)
        _response.raise_for_status()
        token = _response.json().get('id_token')
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })

        # sign in

        login_url = 'https://mobileauth.churchofjesuschrist.org/v1/mobile/login'
        _json = {
            'username': settings.church_username,
            'password': settings.church_password
        }
        _response = self.session.post(login_url, json=_json)
        _response.raise_for_status()
        cookie_name = _response.json().get('name')
        cookie_value = _response.json().get('value')
        self.session.cookies.update({
            cookie_name: cookie_value
        })

        # get home unit number

        user_detail_url = 'https://wam-membertools-api.churchofjesuschrist.org/api/v4/user'
        _response = self.session.get(user_detail_url)
        _response.raise_for_status()
        log.debug(_response.json())
        self.unit_number = _response.json().get('homeUnits')[0]

    def get_unit_members(self):
        url = 'https://wam-membertools-api.churchofjesuschrist.org/api/v4/sync?manual=true'
        _json = [
            {
                'since': int((datetime.datetime.now() - datetime.timedelta(days=85)).timestamp()),
                'types': [
                    'HOUSEHOLDS'
                ],
                'unitNumbers': [
                    self.unit_number
                ]
            }
        ]
        _response = self.session.post(url, json=_json)
        _data = _response.json()
        return _data
