# -*- coding: utf-8 -*-
from django.test import TestCase
from django.test.utils import override_settings

from treemap.audit import FieldPermission
from treemap.lib.object_caches import (clear_caches, role_permissions,
                                     permissions)
from treemap.models import InstanceUser
from treemap.tests import (make_instance, make_commander_user,
                           make_user)

WRITE = FieldPermission.WRITE_DIRECTLY
READ = FieldPermission.READ_ONLY

@override_settings(USE_OBJECT_CACHES=True)
class PermissionsCacheTest(TestCase):
    def setUp(self):
        clear_caches()
        self.instance = make_instance()
        self.user = make_commander_user(self.instance)
        self.role = self.user.get_role(self.instance)

        self.simple_user = make_user()
        default_role = self.instance.default_role
        FieldPermission(model_name='Plot', field_name='geom',
                        role=default_role, instance=self.instance,
                        permission_level=READ).save()

    def get_permission(self, perms, field_name, expectedCount):
        perms = [p for p in perms if p.field_name == field_name]
        self.assertEqual(len(perms), expectedCount)
        return perms[0] if expectedCount == 1 else None

    def get_role_permission(self, role, expectedCount, model_name='Plot',
                            field_name='geom'):
        perms = role_permissions(role, self.instance, model_name)
        return self.get_permission(perms, field_name, expectedCount)

    def get_user_permission(self, user, expectedCount, model_name='Plot',
                            field_name='geom'):
        perms = permissions(user, self.instance, model_name)
        return self.get_permission(perms, field_name, expectedCount)

    def assert_role_permission(self, role, level, model_name='Plot',
                               field_name='geom'):
        perm = self.get_role_permission(role, 1, model_name, field_name)
        self.assertEqual(level, perm.permission_level)

    def assert_user_permission(self, user, level, model_name='Plot',
                               field_name='geom'):
        perm = self.get_user_permission(user, 1, model_name, field_name)
        self.assertEqual(level, perm.permission_level)

    def set_permission(self, role, level, model_name='Plot', field_name='geom'):
        fp, created = FieldPermission.objects.get_or_create(
            model_name=model_name,
            field_name=field_name,
            role=role,
            instance=self.instance)
        fp.permission_level = level
        fp.save()

    def set_permission_silently(self, role, level, model_name='Plot',
                                field_name='geom'):
        # update() sends no signals, so cache won't be invalidated
        FieldPermission.objects.filter(
            model_name=model_name,
            field_name=field_name,
            role=role,
            instance=self.instance
        ).update(permission_level=level)

    def test_user_permission(self):
        self.assert_user_permission(self.user, WRITE)

    def test_role_permission(self):
        self.assert_role_permission(self.role, WRITE)

    def test_default_role(self):
        self.assert_user_permission(self.simple_user, READ)

    def test_empty_user(self):
        self.assert_user_permission(None, READ)

    def test_empty_model_name(self):
        perms = permissions(self.user, self.instance)
        self.assertEqual(len(perms), 80)

    def test_unknown_model_name(self):
        perms = permissions(self.user, self.instance, 'foo')
        self.assertEqual(len(perms), 0)
        perms = role_permissions(self.role, self.instance, 'foo')
        self.assertEqual(len(perms), 0)

    def test_unknown_field_name(self):
        self.get_user_permission(self.user, 0, 'Plot', 'bar')
        self.get_role_permission(self.role, 0, 'Plot', 'bar')

    def test_user_perm_sees_perm_update(self):
        self.set_permission(self.role, READ)
        self.assert_user_permission(self.user, READ)

    def test_role_perm_sees_perm_update(self):
        self.set_permission(self.role, READ)
        self.assert_role_permission(self.role, READ)

    def test_user_perm_sees_role_update(self):
        iuser = InstanceUser.objects.get(user=self.user)
        iuser.role = self.instance.default_role
        iuser.save_with_user(self.user)
        self.assert_user_permission(self.user, READ)

    def test_user_perm_sees_external_update(self):
        self.assert_user_permission(self.user, WRITE)  # loads cache
        # Simulate external update by setting permission without
        # invalidating the cache, then updating the instance timestamp
        self.set_permission_silently(self.role, READ)
        self.assert_user_permission(self.user, WRITE)
        self.instance.adjuncts_timestamp += 1
        self.instance.save()
        self.assert_user_permission(self.user, READ)

    def test_role_perm_sees_external_update(self):
        self.assert_user_permission(self.user, WRITE)  # loads cache
        # Simulate external update by setting permission without
        # invalidating the cache, then updating the instance timestamp
        self.set_permission_silently(self.role, READ)
        self.assert_role_permission(self.role, WRITE)
        self.instance.adjuncts_timestamp += 1
        self.instance.save()
        self.assert_role_permission(self.role, READ)




