import clrkio.settings
import datetime
import fort

from typing import Dict, List


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
        sql = 'select email, permissions from permissions order by email'
        for record in self.q(sql):
            yield {'email': record['email'], 'permissions': record['permissions'].split()}

    def add_permission(self, email: str, permission: str):
        current_permissions = set(self.get_permissions(email))
        current_permissions.add(permission)
        self.set_permissions(email, sorted(current_permissions))

    def get_permissions(self, email: str) -> List[str]:
        sql = 'select permissions from permissions where email = %(email)s'
        permissions = self.q_val(sql, {'email': email})
        if permissions is None:
            return []
        return sorted(set(permissions.split()))

    def set_permissions(self, email: str, permissions: List[str]):
        params = {'email': email, 'permissions': ' '.join(sorted(set(permissions)))}
        self.u('delete from permissions where email = %(email)s', params)
        if permissions:
            self.u('insert into permissions (email, permissions) values (%(email)s, %(permissions)s)', params)

    def has_permission(self, email: str, permission: str) -> bool:
        return permission in self.get_permissions(email)

    def get_member_changes_recipients(self):
        sql = '''
            select email from permissions where permissions like %(permission_like)s
        '''
        params = {'permission_like': '%member-changes%'}
        return self.q(sql, params)

    # members

    def pre_sync_members(self):
        sql = '''
            update members set synced = false where synced is true
        '''
        self.u(sql)

    def post_sync_members(self) -> List[Dict]:
        sql = '''
            select individual_id, name, birthday, email, age_group, gender
            from members
            where synced is false
        '''
        removed = self.q(sql)
        self.log.debug(f'Removing {len(removed)} members')
        sql = '''
            delete from members where synced is false
        '''
        self.u(sql)
        return removed

    def sync_member(self, params: Dict) -> Dict:
        individual_id = params.get('individual_id')
        self.log.debug(f'Syncing member: {individual_id}')
        result = {'result': 'no-change', 'data': params.copy()}
        existing = self.get_member_by_id(params)
        self.log.debug(f'existing: {existing}')
        if existing is None:
            sql = '''
                insert into members (
                    individual_id, name, birthday, email, phone, age_group, gender, synced
                ) values (
                    %(individual_id)s, %(name)s, %(birthday)s, %(email)s, %(phone)s, %(age_group)s, %(gender)s, true
                )
            '''
            result['result'] = 'added'
        else:
            sql = '''
                update members
                set name = %(name)s, birthday = %(birthday)s, email = %(email)s, phone = %(phone)s,
                    age_group = %(age_group)s, gender = %(gender)s, synced = true
                where individual_id = %(individual_id)s
            '''
            changes = []
            for field in ('name', 'birthday', 'email', 'phone', 'age_group', 'gender'):
                existing_value = existing.get(field)
                new_value = params.get(field)
                if not existing_value == new_value:
                    self.log.debug(f'{individual_id} {field}: {existing_value} -> {new_value}')
                    result['result'] = 'changed'
                    changes.append({'field': field, 'old': existing_value, 'new': new_value})
            result['changes'] = changes
        self.u(sql, params)
        return result

    def get_all_members(self) -> List[Dict]:
        sql = '''
            select individual_id, name, birthday, email, age_group, gender from members
        '''
        return self.q(sql)

    def get_member_by_id(self, params) -> Dict:
        sql = '''
            select individual_id, name, birthday, email, phone, age_group, gender, synced
            from members
            where individual_id = %(individual_id)s
        '''
        return self.q_one(sql, params)

    # metadata and migrations

    def add_schema_version(self, schema_version: int):
        self._version = schema_version
        sql = '''
            insert into schema_versions (schema_version, migration_timestamp)
            values (%(schema_version)s, %(migration_timestamp)s)
        '''
        params = {
            'migration_timestamp': datetime.datetime.utcnow(),
            'schema_version': schema_version
        }
        self.u(sql, params)

    def reset(self):
        self.log.warning('Database reset requested, dropping all tables')
        for table in ('members', 'permissions', 'schema_versions'):
            self.u(f'drop table if exists {table} cascade')

    def migrate(self):
        self.log.info(f'Database schema version is {self.version}')
        if self.version < 1:
            self.log.info('Migrating database to schema version 1')
            self.u('''
                create table schema_versions (
                    schema_version integer primary key,
                    migration_timestamp timestamp
                )
            ''')
            self.u('''
                create table permissions (
                    email text primary key,
                    permissions text
                )
            ''')
            self.u('''
                create table members (
                    individual_id bigint primary key,
                    name text,
                    birthday date,
                    email text,
                    age_group text,
                    gender text,
                    synced boolean
                )
            ''')
            self.add_schema_version(1)
        if self.version < 2:
            self.log.info('Migrating database to schema version 2')
            self.u('''
                alter table members
                add column phone text
            ''')
            self.add_schema_version(2)

    def _table_exists(self, table_name: str) -> bool:
        sql = 'select count(*) table_count from information_schema.tables where table_name = %(table_name)s'
        for record in self.q(sql, {'table_name': table_name}):
            if record['table_count'] == 0:
                return False
        return True

    @property
    def version(self) -> int:
        if self._version is None:
            self._version = 0
            if self._table_exists('schema_versions'):
                sql = 'select max(schema_version) current_version from schema_versions'
                current_version: int = self.q_val(sql)
                if current_version is not None:
                    self._version = current_version
        return self._version
