# Base path for all local paths
work_dir = '../'

# Temporary director for building env archive
temp_dir = "/tmp/projectname-deploy-tmp"

# Env archive file name
arch_name = "projectname.dist.tar.gz"

# Directory on destination server for extract environment
destination_dir = "projectname"

# Variables
# Built in variables: VERSION, ENV, DESTINATION_DIR, DOCKER_PROJECT_NAME
# Use $VARNAME variables in path and ${VARNAME} in file content
variables = {
    'DOCKER_PROJECT_NAME': 'projectname',
    'SUDO': 'sudo'
}

# Replace content variables only if file name match pattern
replace_vars_file_patterns = ['.conf$', '.yml$', 'default$']

# Run command
run_command = "cd $DESTINATION_DIR && docker-compose -p $DOCKER_PROJECT_NAME up -d"

# Containers
containers = [
    {
        'name': 'projectname-first-container:$VERSION',
        'registry': 'registry.projectname.com:5000',
        'dockerfile': 'docker/projectname/Dockerfile',
        'build_path': '',
        'build_args': ['VERSION=$VERSION'],
        'arch_name': 'projectname.tar'
    }
]

# Environment files or dirs
files = [
    {'path': 'docker/docker-compose.yml', 'env_path': 'docker-compose.yml', 'replace_vars': True},
    {'path': 'docker/nginx', 'env_path': 'nginx', 'replace_vars': True},
    {'path': 'docker/grafana', 'env_path': 'grafana', 'replace_vars': False},
    {'path': 'docker/influx', 'env_path': 'influx', 'replace_vars': False},
    {'path': 'docker/clickhouse', 'env_path': 'clickhouse', 'replace_vars': False},
    {'path': 'docker/telegraf', 'env_path': 'telegraf', 'replace_vars': False},
    {'path': 'config/config_$ENV.yml', 'env_path': 'config/config_$ENV.yml', 'replace_vars': True},
]

user_commands = {
    'init': {
        'place': 'remote',
        'commands': [
            # Install docker
            '$SUDO apt-get update',
            '$SUDO apt-get install apt-transport-https ca-certificates curl software-properties-common',
            'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | $SUDO apt-key add -',
            '$SUDO add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu  $(lsb_release -cs)  stable"',
            '$SUDO apt-get update',
            '$SUDO apt-get install docker-ce',

            # Install docker compose
            '$SUDO curl -L "https://github.com/docker/compose/releases/download/1.24.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
            '$SUDO chmod +x /usr/local/bin/docker-compose',

            # Add user to docker group
            '$SUDO usermod -aG  docker `whoami`'
        ]
    },
    'hello': {
        'place': 'local',
        'commands': [
            'echo "hello world"'
        ],
    },
    'hello-remote': {
        'place': 'remote',
        'commands': [
            'echo "hello world on server: $SERVER_NAME"'
        ],
    }
}

# Servers config
servers = {
    'dev': {
        'host': 'projectname-dev',
        'version': '0.0.1',
        'env': 'dev',
        'destination_dir': 'projectname',
        'variables': {
            'DOMAIN': 'projectname.local'
        }
    },
    'prod': {
        'host': 'projectname-prod',
        'version': '0.0.1',
        'env': 'prod',
        'destination_dir': 'projectname',
        'variables': {
            'DOMAIN': 'projectname.com',
            'SUDO': ''
        }
    },
}
