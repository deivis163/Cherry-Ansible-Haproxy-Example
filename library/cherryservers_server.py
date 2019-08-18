#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: cherryservers_server
short_description: Manage a bare metal servers at Cherry Servers.
description:
     - Manage a bare metal servers at Cherry Servers.
     - This module has a dependency on cherry >= 0.1.
version_added: "0.1"
options:
  state:
    description:
     - Define desired state of the server.
     - If set to C(present), the module will return back immediately after API call returns.
     - If set to C(active), the module will wait for I(wait_timeout) for server to be in C(active) state.
    default: present
    choices: ['absent', 'active', 'rebooted', 'present', 'stopped', 'running']
  wait_timeout:
    description:
     - How long to wait for server to reach 'active' state.
    default: 1800
  auth_token:
    description:
      - Authenticating API token provided by Cherry Servers. You can supply it via
        CHERRY_AUTH_TOKEN environement variable.
    required: true
  project_id:
    description:
      - ID of project of the servers.
    required: true
  hostname:
    description:
      - Define hostname of server.
  image:
    description:
      - Image to install on the server, e.g. 'Ubuntu 16.04 64bit'.
  ip_address:
    description:
      - List of floating IP addresses to add to new server.
  ip_address_id:
    description:
      -  List of floating IP addresses UIDs to add to new server.
  plan_id:
    description:
      - Plan for server creation.
  ssh_key_id:
    description:
      - SSH key`s ID to add SSH key to server.
  ssh_label:
    description:
      - SSH key`s label to add SSH key to server.
  server_ids:
    description:
      - List of server`s IDs on which to operate.
  region:
    description:
      - Region of the server.
  cout:
    description:
      - Amount of servers to create.
    default: 1
  count_offset:
    description:
      - From which number to start the count.
    default: 1
requirements:
  - "cherry"
  - "python >= 2.6"
author:
  -  "Arturas Razinskij <arturas.razinskij@cherryservers.com>"
'''

EXAMPLES = '''
# Some examples on how to manage servers
# Deploy server with added SSH key in it
- name: Cherry Servers API module
  connection: local
  hosts: localhost
  tasks:
  - name: Deploy CherryServers Server
    cherryservers_server:
      hostname:
        - server%02d.example.com
      plan_id: '161'
      project_id: '79813'
      image: 'Ubuntu 16.04 64bit'
      region: 'EU-East-1'
      state: present
      count: 1
      count_offset: 4
      ssh_label:
        - john
        - marius
# Cancel several servers
- name: Cherry Servers API module
  connection: local
  hosts: localhost
  tasks:
  - name: Remove CherryServers server
    cherryservers_server:
      project_id: '79813'
      hostname:
        - 'server03.example.com'
        - 'server04.example.com'
        - 'server06.example.com'
      state: absent
# Deploy several servers and wait to them to be active
- name: Cherry Servers API module
  connection: local
  hosts: localhost
  tasks:
  - name: Deploy CherryServers Server
    cherryservers_server:
      hostname:
        - server%02d.example.com
      plan_id: '161'
      project_id: '79813'
      image: 'Ubuntu 16.04 64bit'
      region: 'EU-East-1'
      state: active
      count: 2
      count_offset: 1
'''

RETURN = '''
changed:
    description: True if server was added, modified or removed.
    type: bool
    sample: True
    returned: always
server:
    description: Info of IP address that was added, modified or removed.
    type: list
    sample: [
        {
            "hostname": "server05.example.com",
            "image": "Ubuntu 16.04 64bit",
            "href": "/servers/167939",
            "id": 167939,
            "name": "E5-1620v4",
            "state": "pending"
        }
    ]
    returned: always
'''

import os
import time

from ansible.module_utils.basic import AnsibleModule

HAS_CHERRYSERVERS_SDK = True

try:
    import cherry
except ImportError:
    HAS_CHERRYSERVERS_SDK = False

MODULE_STATES = ['absent', 'active', 'rebooted', 'present', 'stopped', 'running']

NAME_REGEX = r'({0}|{0}{1}*{0})'.format(r'[a-zA-Z0-9]', r'[a-zA-Z0-9\-]')
HOSTNAME_REGEX = r'({0}\.)*{0}$'.format(NAME_REGEX)

def run_module():

    module_args = dict(
        auth_token = dict(default=os.environ.get('CHERRY_AUTH_TOKEN'),
                          type = 'str',
                          no_log = True),
        hostname = dict(type = 'list'),
        new=dict(type='bool', required=False, default=False),
        count = dict(type = 'int', default = 1),
        count_offset = dict(type='int', default = 1),
        image = dict(),
        plan_id = dict(type = 'int'),
        project_id = dict(type = 'int', required = True),
        server_id = dict(type='int'),
        server_ids = dict(type='list'),
        ip_address = dict(type='list'),
        ip_address_id = dict(type='list'),
        region  = dict(),
        ssh_key_id = dict(type = 'list'),
        ssh_label = dict(type = 'list'),
        state = dict(choices = MODULE_STATES, default = 'present'),
        wait_timeout = dict(type = 'int', default = 1800)

    )

    mutually_exclusive = [
        ('hostname', 'server_ids'),
        ('ssh_key_id', 'ssh_label')
    ]

    required_one_of = [
        ('hostname', 'server_ids', 'server_id')
    ]

    result = dict(
        changed=False,
        original_message='',
        message=''
    )

    module = AnsibleModule(
        argument_spec=module_args,
        required_one_of = required_one_of,
        mutually_exclusive = mutually_exclusive,
        supports_check_mode=True
    )

    if not HAS_CHERRYSERVERS_SDK:
        module.fail_json(msg='cherry required for this module')

    if not module.params.get('auth_token'):
        module.fail_json(msg='The "auth_token" parameter or ' +
            'CHERRY_AUTH_TOKEN environment variable is required')

    cherryservers_conn = cherry.Master(auth_token=module.params['auth_token'])

    state = module.params['state']

    if state in ('present', 'active'):
        (changed, server) = create_multiple_servers(module, cherryservers_conn)

        if state == 'active':
            deploying_servers_ids = []

            if server:
                for srv in server:
                    srv_id = srv['id']
                    deploying_servers_ids.append(srv_id)

            server = wait_for_resource(module, cherryservers_conn, deploying_servers_ids)

    elif state == 'absent':

        (changed, server) = terminate_multiple_servers(module, cherryservers_conn)

    elif state in ('running', 'stopped', 'rebooted'):

        (changed, server) = servers_power(module, cherryservers_conn)
   
    else:
        raise Exception("Unknown state: %s" % state)

    if module.check_mode:
        return result

    result['server'] = server
    result['changed'] = changed

    module.exit_json(**result)


def provide_hostnames(module, cherryservers_conn):

    """ 
    Function for provide formatted list of hostnames
    Returns list of hostnames
    """

    count =  module.params['count']
    count_offset = module.params['count_offset']
    hostname = module.params['hostname']

    if len(hostname) == 1:
        hostname = hostname[0]

        if '%' in hostname:
            count_range = range(count_offset, count_offset + count)
            hostnames = [hostname % i for i in count_range]
        else:
            hostnames = [hostname] * count
    else:
        if count > 1:
            raise Exception("If you set several hostnames "
                "don't use \"count\" larger than 1.")
        hostnames = hostname

    # msg = "Type: %s Lenght: %s Hostnames: %s" % (type(hostname), len(hostname), hostnames)
    # raise Exception(msg)

    return hostnames

def get_ids_for_keys(module, cherryservers_conn):

    """
    Function that returns ssh key ids on exit with
    input as label, key_id.
    """

    labels = module.params['ssh_label']
    key_id = module.params['ssh_key_id']

    ssh_keys = cherryservers_conn.get_ssh_keys()

    if labels:
        items = labels
        ssh_keys_dict = {"%s" % ssh_key['id'] : "%s" 
            % ssh_key['label'] for ssh_key in ssh_keys}

    elif key_id:
        items = key_id
        ssh_keys_dict = {"%s" % ssh_key['id'] : "%s" 
            % ssh_key['id'] for ssh_key in ssh_keys}

    else:
        msg = ("Unknown ssh key identifier, use one of: "
        "label, key_file, key, key_id, fingerprint")
        module.fail_json(msg=msg)

    uniq_dict = {}
    non_uniq_dict = {}

    for item in items:
        list_of_keys = []
        for key,value in ssh_keys_dict.items():
            if value == item:
                list_of_keys.append(key)
                uniq_dict[key] = value

        if len(list_of_keys) > 1:
            for key in list_of_keys:
                non_uniq_dict[key] = item

            msg = ("There are several keys with same value: %s. Please "
            "use \"ids\" in that case." % non_uniq_dict)
            module.fail_json(msg=msg)

    return list(uniq_dict.keys())

def servers_power(module, cherryservers_conn):

    """
    Function to control power of several servers
    """

    state = module.params['state']

    changed = False

    servers = []
    changes = []

    server_ids = module.params['server_ids']

    if module.params['hostname']:

        hostnames = provide_hostnames(module, cherryservers_conn)
        server_ids = get_ids_from_hostnames(module, cherryservers_conn, hostnames)

    for server_id in server_ids:
        (changed, server) = server_power(module, cherryservers_conn, server_id, state)

        servers.append(server)
        changes.append(changed)

    if True in changes:
        changed = True

    return (changed, servers)

def server_power(module, cherryservers_conn, server_id, state):

    """
    Function to control server`s power
    """

    if state == 'stopped':
        server = cherryservers_conn.poweroff_server(server_id)
    elif state == 'running':
        server = cherryservers_conn.poweron_server(server_id)
    elif state == 'rebooted':
        server = cherryservers_conn.reboot_server(server_id)
    else:
        raise Exception("Unknown power state: %s" % state)

    check_for_errors(module, server)

    changed = True
    
    return (changed, server)

def get_id_of_floating_ip(module, cherryservers_conn):

    """
    In order to remove floating IP by it's numeric IP
    address, we need to translate that IP to its UID
    Functions returns list or UIDs.
    """

    project_id = module.params['project_id']
    ip_address = module.params['ip_address']
    ip_address_id = module.params['ip_address_id']

    current_ips = cherryservers_conn.get_ip_addresses(project_id)

    check_for_errors(module, current_ips)

    if ip_address:
        items = ip_address
        keys_dict = {"%s" % ip['id'] : "%s" % ip['address'] 
            for ip in current_ips 
                if ip['type'] == 'floating-ip'}
    elif ip_address_id:
        items = ip_address_id
        keys_dict = {"%s" % ip['id'] : "%s" % ip['id'] 
            for ip in current_ips 
                if ip['type'] == 'floating-ip'}
    else:
        return

    uniq_dict = {}

    for item in items:
        for key,value in keys_dict.items():
            if value == item:
                uniq_dict[key] = value

    return list(uniq_dict.keys())

def create_multiple_servers(module, cherryservers_conn):

    """
    Function for deploying multiple servers.
    """

    changed = False

    servers = []
    changes = []
    key_ids = []

    if module.params['ssh_label'] or module.params['ssh_key_id']:
        key_ids = get_ids_for_keys(module, cherryservers_conn)

    if module.params['ip_address'] or module.params['ip_address_id']:

        floating_ip_uids = get_id_of_floating_ip(module, cherryservers_conn)
        count = module.params['count']

        if count > 1:
            msg = ("You can add floating IP only to one server at a time. Don't use "
            "count greater then 1. Current value: %s" % count)
            module.fail_json(msg=msg)
    else:
        floating_ip_uids = []

    hostnames = provide_hostnames(module, cherryservers_conn)

    for hostname in hostnames:
        (changed, server) = create_server(module, cherryservers_conn, hostname, key_ids, floating_ip_uids)

        servers.append(server)
        changes.append(changed)

    if True in changes:
        changed = True

    return (changed, servers)

def create_server(module, cherryservers_conn, hostname, ssh_keys, floating_ip_uids):

    """
    Function for deploy of single server.
    """

    required_params = ('project_id', 'image', 'plan_id')

    for param in required_params:
        if not module.params.get(param):
            module.fail_json(
                msg="%s parameter is required for new server." % param)

    project_id = module.params['project_id']
    image = module.params['image']
    region = module.params['region']
    plan_id = module.params['plan_id']

    server = cherryservers_conn.create_server(
        project_id=project_id,
        hostname=hostname,
        image=image,
        region=region,
        ip_addresses=floating_ip_uids,
        ssh_keys=ssh_keys,
        plan_id=plan_id)

    check_for_errors(module, server)
    
    changed = True

    return (changed, server)

def wait_for_resource(module, cherryservers_conn, deploying_servers_ids):

    """
    Function waits for servers to be active ant
    reachable.
    """

    wait_timeout = module.params['wait_timeout']

    wait_step = 10

    wait_timeout = time.time() + wait_timeout

    while wait_timeout > time.time():
        time.sleep(wait_step)

        current_states = []
        current_servers = []
        for server_id in deploying_servers_ids:
            current_server = cherryservers_conn.get_server(server_id)
            if 'id' in current_server:
                current_states.append(current_server['state'])
                current_servers.append(current_server)

        if all(state == 'active' for state in current_states):
            return current_servers

    raise Exception("Timed out waiting for active device: %s" % server_id)

def check_for_errors(module, server):

    """
    Function for handling 404 & 400 errors, so ansible can fail
    in normal way, not with tracebacks.
    """

    if 'code' in server and (server['code'] == 404 or server['code'] == 400):
        return module.fail_json(msg=server['message'])
    else:
        return

def get_ids_from_hostnames(module, cherryservers_conn, hostnames):

    """
    Functions returns list of server_ids getted from hostnames
    in case if hostname is uniq for specified project.
    """

    project_id = module.params['project_id']

    current_servers = cherryservers_conn.get_servers(project_id)

    check_for_errors(module, current_servers)

    sid_host_dict = {"%s" % server['id'] : "%s" % server['hostname'] for server in current_servers}

    # Ensure to return only ids for servers with uniq hostname,
    # if there are servers with same hostname suggest to use
    # server_ids instead.
    uniq_sid_host_dic = {}
    non_uniq_sid_host_dic = {}

    for hostname in hostnames:
        list_of_keys = []
        for key,value in sid_host_dict.items():
            if value == hostname:
                list_of_keys.append(key)
                uniq_sid_host_dic[key] = value
        if len(list_of_keys) > 1:
            for key in list_of_keys:
                non_uniq_sid_host_dic[key] = hostname

            msg = ("There are several servers with same hostname: %s. Please "
            "use \"server_ids\" in that case." % non_uniq_sid_host_dic)
            module.fail_json(msg=msg)

    return list(uniq_sid_host_dic.keys())

def terminate_multiple_servers(module, cherryservers_conn):

    """ 
    Function for termination of several servers.
    Returns 'changed' in case of termination of 
    one of the servers.
    Function doesn't wait for complete termination.
    """

    changed = False

    servers = []
    changes = []

    server_ids = module.params['server_ids']

    if module.params['hostname']:

        hostnames = provide_hostnames(module, cherryservers_conn)
        server_ids = get_ids_from_hostnames(module, cherryservers_conn, hostnames)

    server_ids = set(server_ids)

    for server_id in server_ids:
        (changed, server) = terminate_server(module, cherryservers_conn, server_id)
        servers.append(server)
        changes.append(changed)

    if True in changes:
        changed = True

    return (changed, servers)

def terminate_server(module, cherryservers_conn, server_id):

    """ 
    Function for termination of single server.
    Returns server object if available and 'changed'
    if server was terminated.
    Function doesn't wait for complete termination.
    """

    changed = False

    current_server = cherryservers_conn.get_server(server_id)

    if 'id' in current_server:

        if current_server['state'] == 'terminating':
            server = current_server
            changed = False
        else:
            server = cherryservers_conn.terminate_server(
                server_id=server_id
            )
            changed = True

    elif 'code' in current_server and current_server['code'] == 404:

        server = None
        changed = False

    return (changed, server)

def main():
    run_module()

if __name__ == '__main__':
    main()
