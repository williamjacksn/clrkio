import clrkio.settings
import logging
import requests

log = logging.getLogger(__name__)


class ChurchToolsClient:
    def __init__(self, settings: clrkio.settings.Settings):
        self.settings = settings
        self.session = requests.session()
        self.session.auth = (settings.church_tools_basic_auth_username, settings.church_tools_basic_auth_password)
        self.session.headers.update({
            'lds_api_key': settings.church_tools_api_key,
            'User-Agent': 'Member%20Tools/6544 CFNetwork/978.0.7 Darwin/18.7.0'
        })
        self.session.cookies['ObFormLoginCookie'] = ('wh=www.churchofjesuschrist.org%20wu=%2Fheader%20wo=1%20'
                                                     'rh=https%3A%2F%2Fwww.churchofjesuschrist.org%20ru=%2Fheader')
        log.debug(f'SESSION HEADERS {self.session.headers}')

        # sign in

        _data = {
            'username': settings.church_username,
            'password': settings.church_password
        }
        _headers = {
            'Value': ('wh=www.churchofjesuschrist.org%20wu=%2Fheader%20wo=1%20'
                      'rh=https%3A%2F%2Fwww.churchofjesuschrist.org%20ru=%2Fheader')
        }
        login_url = 'https://signin.churchofjesuschrist.org/login.html'
        _response = self.session.post(login_url, data=_data, headers=_headers, allow_redirects=False)
        log.debug(f'REQUEST HEADERS {_response.request.headers}')
        log.debug(f'RESPONSE HEADERS {_response.headers}')

        # validate

        self.session.headers.update({
            'User-Agent': 'LDS Tools/3.6.4 (org.lds.ldstools; build:6544; iOS 12.4.4) Alamofire/4.8.1'
        })
        validate_url = ('https://ws-mobile.churchofjesuschrist.org/mobiledirectory/services/mobile/v3.0/validator/'
                        'endOfLife/ldstools/3.0')
        _response = self.session.get(validate_url)
        log.debug(f'REQUEST HEADERS {_response.request.headers}')
        log.debug(f'RESPONSE HEADERS {_response.headers}')

        # get home unit number

        user_detail_url = ('https://ws-mobile.churchofjesuschrist.org/mobiledirectory/services/mobile/v3.0/ldstools/'
                           'current-user-detail?lang=eng')
        _response = self.session.get(user_detail_url)
        self.unit_number = _response.json().get('homeUnitNbr')

    def get_unit_members(self):
        url = (f'https://ws-mobile.churchofjesuschrist.org/mobiledirectory/services/mobile/v3.0/ldstools/'
               f'member-detaillist-with-callings/{self.unit_number}?lang=eng')
        _response = self.session.get(url)
        _data = _response.json()
        return _data
