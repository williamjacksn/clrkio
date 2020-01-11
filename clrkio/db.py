import clrkio.settings
import datetime
import fort

from typing import List

class Database(fort.PostgresDatabase):
    _version: int = None
    settings: clrkio.settings.Settings

    def __init__(self, settings: clrkio.settings.Settings):
        super().__init__(settings.db)
        self.settings = settings

    # users and permissions

    def bootstrap_admin(self):
        if self.settings.bootstrap_admin in (None, ''):
            return
        self.log.info(f'Adding a bootstrap admin: {self.settings.bootstrap_admin}')
        self.add_permission(self.settings.bootstrap_admin, 'admin')

    def get_users(self):
        sql = 'SELECT email, permissions FROM permissions ORDER BY email'
        for record in self.q(sql):
            yield {'email': record['email'], 'permissions': record['permissions'].split()}

    def add_permission(self, email: str, permission: str):
        current_permissions = set(self.get_permissions(email))
        current_permissions.add(permission)
        self.set_permissions(email, sorted(current_permissions))

    def get_permissions(self, email: str) -> List[str]:
        sql = 'SELECT permissions FROM permissions WHERE email = %(email)s'
        permissions = self.q_val(sql, {'email': email})
        if permissions is None:
            return []
        return sorted(set(permissions.split()))

    def set_permissions(self, email: str, permissions: List[str]):
        params = {'email': email, 'permissions': ' '.join(sorted(set(permissions)))}
        self.u('DELETE FROM permissions WHERE email = %(email)s', params)
        if permissions:
            self.u('INSERT INTO permissions (email, permissions) VALUES (%(email)s, %(permissions)s)', params)

    def has_permission(self, email: str, permission: str) -> bool:
        return permission in self.get_permissions(email)

    # members

    def get_all_members(self):
        return []

    def get_member_by_id(self, _id):
        return {}

    # metadata and migrations

    def add_schema_version(self, schema_version: int):
        self._version = schema_version
        sql = '''
            INSERT INTO schema_versions (schema_version, migration_timestamp)
            VALUES (%(schema_version)s, %(migration_timestamp)s)
        '''
        params = {
            'migration_timestamp': datetime.datetime.utcnow(),
            'schema_version': schema_version
        }
        self.u(sql, params)

    def reset(self):
        self.log.warning('Database reset requested, dropping all tables')
        for table in ('members', 'permissions', 'schema_versions'):
            self.u(f'DROP TABLE IF EXISTS {table} CASCADE')

    def migrate(self):
        self.log.info(f'Database schema version is {self.version}')
        if self.version < 1:
            self.log.info('Migrating database to schema version 1')
            self.u('''
                CREATE TABLE schema_versions (
                    schema_version integer PRIMARY KEY,
                    migration_timestamp timestamp
                )
            ''')
            self.u('''
                CREATE TABLE permissions (
                    email text PRIMARY KEY,
                    permissions text
                )
            ''')
            self.u('''
                CREATE TABLE members (
                    individual_id bigint PRIMARY KEY,
                    name text,
                    birthday date,
                    email text
                )
            ''')
            self.add_schema_version(1)

    def _table_exists(self, table_name: str) -> bool:
        sql = 'SELECT count(*) table_count FROM information_schema.tables WHERE table_name = %(table_name)s'
        for record in self.q(sql, {'table_name': table_name}):
            if record['table_count'] == 0:
                return False
        return True

    @property
    def version(self) -> int:
        if self._version is None:
            self._version = 0
            if self._table_exists('schema_versions'):
                sql = 'SELECT max(schema_version) current_version FROM schema_versions'
                current_version: int = self.q_val(sql)
                if current_version is not None:
                    self._version = current_version
        return self._version
