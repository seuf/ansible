#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2017, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: ipa_host
author: Thomas Krahn (@Nosmoht)
short_description: Manage FreeIPA host
description:
- Add, modify and delete an IPA host using IPA API
options:
  fqdn:
    description:
    - Full qualified domain name.
    - Can not be changed as it is the unique identifier.
    required: true
    aliases: ["name"]
  description:
    description:
    - A description of this host.
    required: false
  force:
    description:
    - Force host name even if not in DNS.
    required: false
  ip_address:
    description:
    - Add the host to DNS with this IP address.
    required: false
  mac_address:
    description:
    - List of Hardware MAC address(es) off this host.
    - If option is omitted MAC addresses will not be checked or changed.
    - If an empty list is passed all assigned MAC addresses will be removed.
    - MAC addresses that are already assigned but not passed will be removed.
    required: false
    aliases: ["macaddress"]
  ns_host_location:
    description:
    - Host location (e.g. "Lab 2")
    required: false
    aliases: ["nshostlocation"]
  ns_hardware_platform:
    description:
    - Host hardware platform (e.g. "Lenovo T61")
    required: false
    aliases: ["nshardwareplatform"]
  ns_os_version:
    description:
    - Host operating system and version (e.g. "Fedora 9")
    required: false
    aliases: ["nsosversion"]
  user_certificate:
    description:
    - List of Base-64 encoded server certificates.
    - If option is omitted certificates will not be checked or changed.
    - If an empty list is passed all assigned certificates will be removed.
    - Certificates already assigned but not passed will be removed.
    required: false
    aliases: ["usercertificate"]
  state:
    description: State to ensure
    required: false
    default: present
    choices: ["present", "absent", "disabled"]
  ipa_port:
    description: Port of IPA server
    required: false
    default: 443
  ipa_host:
    description: IP or hostname of IPA server
    required: false
    default: ipa.example.com
  ipa_user:
    description: Administrative account used on IPA server
    required: false
    default: admin
  ipa_pass:
    description: Password of administrative user
    required: true
  ipa_prot:
    description: Protocol used by IPA server
    required: false
    default: https
    choices: ["http", "https"]
  validate_certs:
    description:
    - This only applies if C(ipa_prot) is I(https).
    - If set to C(no), the SSL certificates will not be validated.
    - This should only set to C(no) used on personally controlled sites using self-signed certificates.
    required: false
    default: true
version_added: "2.3"
'''

EXAMPLES = '''
# Ensure host is present
- ipa_host:
    name: host01.example.com
    description: Example host
    ip_address: 192.168.0.123
    ns_host_location: Lab
    ns_os_version: CentOS 7
    ns_hardware_platform: Lenovo T61
    mac_address:
    - "08:00:27:E3:B1:2D"
    - "52:54:00:BD:97:1E"
    state: present
    ipa_host: ipa.example.com
    ipa_user: admin
    ipa_pass: topsecret

# Ensure host is disabled
- ipa_host:
    name: host01.example.com
    state: disabled
    ipa_host: ipa.example.com
    ipa_user: admin
    ipa_pass: topsecret

# Ensure that all user certificates are removed
- ipa_host:
    name: host01.example.com
    user_certificate: []
    ipa_host: ipa.example.com
    ipa_user: admin
    ipa_pass: topsecret

# Ensure host is absent
- ipa_host:
    name: host01.example.com
    state: absent
    ipa_host: ipa.example.com
    ipa_user: admin
    ipa_pass: topsecret
'''

RETURN = '''
host:
  description: Host as returned by IPA API.
  returned: always
  type: dict
host_diff:
  description: List of options that differ and would be changed
  returned: if check mode and a difference is found
  type: list
'''

import traceback

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ipa import IPAClient
from ansible.module_utils._text import to_native


class HostIPAClient(IPAClient):
    def __init__(self, module, host, port, protocol):
        super(HostIPAClient, self).__init__(module, host, port, protocol)

    def host_find(self, name):
        return self._post_json(method='host_find', name=None, item={'all': True, 'fqdn': name})

    def host_add(self, name, host):
        return self._post_json(method='host_add', name=name, item=host)

    def host_mod(self, name, host):
        return self._post_json(method='host_mod', name=name, item=host)

    def host_del(self, name):
        return self._post_json(method='host_del', name=name)

    def host_disable(self, name):
        return self._post_json(method='host_disable', name=name)


def get_host_dict(description=None, force=None, ip_address=None, ns_host_location=None, ns_hardware_platform=None,
                  ns_os_version=None, user_certificate=None, mac_address=None):
    data = {}
    if description is not None:
        data['description'] = description
    if force is not None:
        data['force'] = force
    if ip_address is not None:
        data['ip_address'] = ip_address
    if ns_host_location is not None:
        data['nshostlocation'] = ns_host_location
    if ns_hardware_platform is not None:
        data['nshardwareplatform'] = ns_hardware_platform
    if ns_os_version is not None:
        data['nsosversion'] = ns_os_version
    if user_certificate is not None:
        data['usercertificate'] = [{"__base64__": item} for item in user_certificate]
    if mac_address is not None:
        data['macaddress'] = mac_address
    return data


def get_host_diff(client, ipa_host, module_host):
    non_updateable_keys = ['force', 'ip_address']
    for key in non_updateable_keys:
        if key in module_host:
            del module_host[key]

    return client.get_diff(ipa_data=ipa_host, module_data=module_host)


def ensure(module, client):
    name = module.params['fqdn']
    state = module.params['state']

    ipa_host = client.host_find(name=name)
    module_host = get_host_dict(description=module.params['description'],
                                force=module.params['force'], ip_address=module.params['ip_address'],
                                ns_host_location=module.params['ns_host_location'],
                                ns_hardware_platform=module.params['ns_hardware_platform'],
                                ns_os_version=module.params['ns_os_version'],
                                user_certificate=module.params['user_certificate'],
                                mac_address=module.params['mac_address'])
    changed = False
    if state in ['present', 'enabled', 'disabled']:
        if not ipa_host:
            changed = True
            if not module.check_mode:
                client.host_add(name=name, host=module_host)
        else:
            diff = get_host_diff(client, ipa_host, module_host)
            if len(diff) > 0:
                changed = True
                if not module.check_mode:
                    data = {}
                    for key in diff:
                        data[key] = module_host.get(key)
                    client.host_mod(name=name, host=data)

    else:
        if ipa_host:
            changed = True
            if not module.check_mode:
                client.host_del(name=name)

    return changed, client.host_find(name=name)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            description=dict(type='str', required=False),
            fqdn=dict(type='str', required=True, aliases=['name']),
            force=dict(type='bool', required=False),
            ip_address=dict(type='str', required=False),
            ns_host_location=dict(type='str', required=False, aliases=['nshostlocation']),
            ns_hardware_platform=dict(type='str', required=False, aliases=['nshardwareplatform']),
            ns_os_version=dict(type='str', required=False, aliases=['nsosversion']),
            user_certificate=dict(type='list', required=False, aliases=['usercertificate']),
            mac_address=dict(type='list', required=False, aliases=['macaddress']),
            state=dict(type='str', required=False, default='present',
                       choices=['present', 'absent', 'enabled', 'disabled']),
            ipa_prot=dict(type='str', required=False, default='https', choices=['http', 'https']),
            ipa_host=dict(type='str', required=False, default='ipa.example.com'),
            ipa_port=dict(type='int', required=False, default=443),
            ipa_user=dict(type='str', required=False, default='admin'),
            ipa_pass=dict(type='str', required=True, no_log=True),
            validate_certs=dict(type='bool', required=False, default=True),
        ),
        supports_check_mode=True,
    )

    client = HostIPAClient(module=module,
                           host=module.params['ipa_host'],
                           port=module.params['ipa_port'],
                           protocol=module.params['ipa_prot'])

    try:
        client.login(username=module.params['ipa_user'],
                     password=module.params['ipa_pass'])
        changed, host = ensure(module, client)
        module.exit_json(changed=changed, host=host)
    except Exception as e:
        module.fail_json(msg=to_native(e), exception=traceback.format_exc())

if __name__ == '__main__':
    main()
