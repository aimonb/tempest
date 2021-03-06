# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from tempest.api.compute import base
from tempest.common.utils.data_utils import rand_name
from tempest import exceptions
from tempest.test import attr


class QuotasAdminTestJSON(base.BaseComputeAdminTest):
    _interface = 'json'

    @classmethod
    def setUpClass(cls):
        super(QuotasAdminTestJSON, cls).setUpClass()
        cls.auth_url = cls.config.identity.uri
        cls.client = cls.os.quotas_client
        cls.adm_client = cls.os_adm.quotas_client
        cls.identity_admin_client = cls._get_identity_admin_client()
        cls.sg_client = cls.security_groups_client

        resp, tenants = cls.identity_admin_client.list_tenants()

        # NOTE(afazekas): these test cases should always create and use a new
        # tenant most of them should be skipped if we can't do that
        if cls.config.compute.allow_tenant_isolation:
            cls.demo_tenant_id = cls.isolated_creds.get_primary_user().get(
                'tenantId')
        else:
            cls.demo_tenant_id = [tnt['id'] for tnt in tenants if tnt['name']
                                  == cls.config.identity.tenant_name][0]

        cls.default_quota_set = set(('injected_file_content_bytes',
                                     'metadata_items', 'injected_files',
                                     'ram', 'floating_ips',
                                     'fixed_ips', 'key_pairs',
                                     'injected_file_path_bytes',
                                     'instances', 'security_group_rules',
                                     'cores', 'security_groups'))

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            try:
                cls.servers_client.delete_server(server['id'])
            except exceptions.NotFound:
                continue
        super(QuotasAdminTestJSON, cls).tearDownClass()

    @attr(type='smoke')
    def test_get_default_quotas(self):
        # Admin can get the default resource quota set for a tenant
        expected_quota_set = self.default_quota_set | set(['id'])
        resp, quota_set = self.client.get_default_quota_set(
            self.demo_tenant_id)
        self.assertEqual(200, resp.status)
        self.assertEqual(sorted(expected_quota_set),
                         sorted(quota_set.keys()))
        self.assertEqual(quota_set['id'], self.demo_tenant_id)

    @attr(type='gate')
    def test_update_all_quota_resources_for_tenant(self):
        # Admin can update all the resource quota limits for a tenant
        resp, default_quota_set = self.client.get_default_quota_set(
            self.demo_tenant_id)
        new_quota_set = {'injected_file_content_bytes': 20480,
                         'metadata_items': 256, 'injected_files': 10,
                         'ram': 10240, 'floating_ips': 20, 'fixed_ips': 10,
                         'key_pairs': 200, 'injected_file_path_bytes': 512,
                         'instances': 20, 'security_group_rules': 20,
                         'cores': 2, 'security_groups': 20}
        # Update limits for all quota resources
        resp, quota_set = self.adm_client.update_quota_set(
            self.demo_tenant_id,
            force=True,
            **new_quota_set)

        default_quota_set.pop('id')
        self.addCleanup(self.adm_client.update_quota_set,
                        self.demo_tenant_id, **default_quota_set)
        self.assertEqual(200, resp.status)
        self.assertEqual(new_quota_set, quota_set)

    # TODO(afazekas): merge these test cases
    @attr(type='gate')
    def test_get_updated_quotas(self):
        # Verify that GET shows the updated quota set
        tenant_name = rand_name('cpu_quota_tenant_')
        tenant_desc = tenant_name + '-desc'
        identity_client = self.os_adm.identity_client
        _, tenant = identity_client.create_tenant(name=tenant_name,
                                                  description=tenant_desc)
        tenant_id = tenant['id']
        self.addCleanup(identity_client.delete_tenant,
                        tenant_id)

        self.adm_client.update_quota_set(tenant_id,
                                         ram='5120')
        resp, quota_set = self.adm_client.get_quota_set(tenant_id)
        self.assertEqual(200, resp.status)
        self.assertEqual(quota_set['ram'], 5120)

    # TODO(afazekas): Add dedicated tenant to the skiped quota tests
    # it can be moved into the setUpClass as well
    @attr(type='gate')
    def test_create_server_when_cpu_quota_is_full(self):
        # Disallow server creation when tenant's vcpu quota is full
        resp, quota_set = self.client.get_quota_set(self.demo_tenant_id)
        default_vcpu_quota = quota_set['cores']
        vcpu_quota = 0  # Set the quota to zero to conserve resources

        resp, quota_set = self.adm_client.update_quota_set(self.demo_tenant_id,
                                                           force=True,
                                                           cores=vcpu_quota)

        self.addCleanup(self.adm_client.update_quota_set, self.demo_tenant_id,
                        cores=default_vcpu_quota)
        self.assertRaises(exceptions.OverLimit, self.create_server)

    @attr(type='gate')
    def test_create_server_when_memory_quota_is_full(self):
        # Disallow server creation when tenant's memory quota is full
        resp, quota_set = self.client.get_quota_set(self.demo_tenant_id)
        default_mem_quota = quota_set['ram']
        mem_quota = 0  # Set the quota to zero to conserve resources

        self.adm_client.update_quota_set(self.demo_tenant_id,
                                         force=True,
                                         ram=mem_quota)

        self.addCleanup(self.adm_client.update_quota_set, self.demo_tenant_id,
                        ram=default_mem_quota)
        self.assertRaises(exceptions.OverLimit, self.create_server)

    @attr(type='gate')
    def test_update_quota_normal_user(self):
        self.assertRaises(exceptions.Unauthorized,
                          self.client.update_quota_set,
                          self.demo_tenant_id,
                          ram=0)

    @attr(type=['negative', 'gate'])
    def test_create_server_when_instances_quota_is_full(self):
        # Once instances quota limit is reached, disallow server creation
        resp, quota_set = self.client.get_quota_set(self.demo_tenant_id)
        default_instances_quota = quota_set['instances']
        instances_quota = 0  # Set quota to zero to disallow server creation

        self.adm_client.update_quota_set(self.demo_tenant_id,
                                         force=True,
                                         instances=instances_quota)
        self.addCleanup(self.adm_client.update_quota_set, self.demo_tenant_id,
                        instances=default_instances_quota)
        self.assertRaises(exceptions.OverLimit, self.create_server)

    @attr(type=['negative', 'gate'])
    def test_security_groups_exceed_limit(self):
        # Negative test: Creation Security Groups over limit should FAIL

        resp, quota_set = self.client.get_quota_set(self.demo_tenant_id)
        default_sg_quota = quota_set['security_groups']
        sg_quota = 0  # Set the quota to zero to conserve resources

        resp, quota_set =\
            self.adm_client.update_quota_set(self.demo_tenant_id,
                                             force=True,
                                             security_groups=sg_quota)

        self.addCleanup(self.adm_client.update_quota_set,
                        self.demo_tenant_id,
                        security_groups=default_sg_quota)

        # Check we cannot create anymore
        self.assertRaises(exceptions.OverLimit,
                          self.sg_client.create_security_group,
                          "sg-overlimit", "sg-desc")

    @attr(type=['negative', 'gate'])
    def test_security_groups_rules_exceed_limit(self):
        # Negative test: Creation of Security Group Rules should FAIL
        # when we reach limit maxSecurityGroupRules

        resp, quota_set = self.client.get_quota_set(self.demo_tenant_id)
        default_sg_rules_quota = quota_set['security_group_rules']
        sg_rules_quota = 0  # Set the quota to zero to conserve resources

        resp, quota_set =\
            self.adm_client.update_quota_set(
                self.demo_tenant_id,
                force=True,
                security_group_rules=sg_rules_quota)

        self.addCleanup(self.adm_client.update_quota_set,
                        self.demo_tenant_id,
                        security_group_rules=default_sg_rules_quota)

        s_name = rand_name('securitygroup-')
        s_description = rand_name('description-')
        resp, securitygroup =\
            self.sg_client.create_security_group(s_name, s_description)
        self.addCleanup(self.sg_client.delete_security_group,
                        securitygroup['id'])

        secgroup_id = securitygroup['id']
        ip_protocol = 'tcp'

        # Check we cannot create SG rule anymore
        self.assertRaises(exceptions.OverLimit,
                          self.sg_client.create_security_group_rule,
                          secgroup_id, ip_protocol, 1025, 1025)


class QuotasAdminTestXML(QuotasAdminTestJSON):
    _interface = 'xml'
