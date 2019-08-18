# Cherry-Ansible-Firewalled-Haproxy-Example

Requirements:

Ansible

SSH key (without passphrase)

Directions

Create an API Key for your CherryServers account at https://portal.cherryservers.com/#/settings/api-keys

Export the key on working terminal session: export CHERRY_AUTH_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXUyJ9"

Create ssh key: ssh-keygen -t rsa -b 4096 -C "your_email@example.com"  (Press enter, do not use any passphrase)

Upload SSH pub keyfrom: /home/user/.ssh/id_rsa.pub to: https://portal.cherryservers.com/#/settings/ssh-keys and enter label name SSHKEY

You will either have to SSH into each of the serves once before running this command or disable host_key_checking for ansible by running:

export ANSIBLE_HOST_KEY_CHECKING=False

Edit main.yml and enter your project ID.

Run ansible playbook with command : ansible-playbook main.yml
