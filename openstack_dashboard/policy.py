# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
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

"""Policy engine for Horizon"""

import logging
import os.path

from django.conf import settings  # noqa

from oslo.config import cfg

from openstack_auth import utils as auth_utils

from openstack_dashboard.openstack.common import policy

LOG = logging.getLogger(__name__)

CONF = cfg.CONF

_ENFORCER = None
_BASE_PATH = getattr(settings, 'POLICY_FILES_PATH', '')


def _get_enforcer():
    global _ENFORCER
    if not _ENFORCER:
        _ENFORCER = {}
        policy_files = getattr(settings, 'POLICY_FILES', {})
        for service in policy_files.keys():
            enforcer = policy.Enforcer()
            enforcer.policy_path = os.path.join(_BASE_PATH,
                                                policy_files[service])
            if os.path.isfile(enforcer.policy_path):
                LOG.debug("adding enforcer for service: %s" % service)
                _ENFORCER[service] = enforcer
            else:
                LOG.warn("policy file for service: %s not found at %s" %
                         (service, enforcer.policy_path))
    return _ENFORCER


def reset():
    global _ENFORCER
    _ENFORCER = None


def check(actions, request, target={}):
    """
    Check if the user has permission to the action according
    to policy setting.

    :param actions: list of scope and action to do policy checks on, the
                    composition of which is (scope, action)

        scope: service type managing the policy for action
        action: string representing the action to be checked

            this should be colon separated for clarity.
            i.e. compute:create_instance
                 compute:attach_volume
                 volume:attach_volume

       for a policy action that requires a single action:
           actions should look like "(("compute", "compute:create_instance"),)"
       for a multiple action check:
           actions should look like "(("identity", "identity:list_users"),
                                      ("identity", "identity:list_roles"))"

    :param request: django http request object. If not specified, credentials
                    must be passed.
    :param target: dictionary representing the object of the action
                      for object creation this should be a dictionary
                      representing the location of the object e.g.
                      {'tenant_id': object.tenant_id}
    :returns: boolean if the user has permission or not for the actions.
    """
    user = auth_utils.get_user(request)
    credentials = _user_to_credentials(request, user)

    enforcer = _get_enforcer()

    for action in actions:
        scope, action = action[0], action[1]
        if scope in enforcer:
            # if any check fails return failure
            if not enforcer[scope].enforce(action, target, credentials):
                return False
        # if no policy for scope, allow action, underlying API will
        # ultimately block the action if not permitted, treat as though
        # allowed
    return True


def _user_to_credentials(request, user):
    if not hasattr(user, "_credentials"):
        roles = [role['name'] for role in user.roles]
        user._credentials = {'user_id': user.id,
                             'token': user.token,
                             'username': user.username,
                             'project_id': user.project_id,
                             'project_name': user.project_name,
                             'domain_id': user.user_domain_id,
                             'is_admin': user.is_superuser,
                             'roles': roles}
    return user._credentials
