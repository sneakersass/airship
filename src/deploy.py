#!/usr/bin/env python3

### START OF CODE
import os
import config
import sys
import re
import signal
import subprocess
import json
import http.client

version = "v1.2.12"

def usage():
    print("AirShip [%s] usage: deploy.py [server name] {commands} {options}" % version)
    print("")
    print("Commands: ")
    print(" build    build and push docker containers to registry")
    print(" deploy   make environment archive, upload it to server, and run")
    print(" init     run init commands on destination server")
    print(" run      execute 'run' command")
    print("")
    print("Options: ")
    print(" -v                   verbose mode, print executed commands")
    print(" --dry                dry run mode, all commands will not executed")
    print(" --skip-containers    skip build, deploy and import docker containers")
    print("")
    print(" --version            print this script version")
    print(" --update             update this script")


# -- Lib

def mes(text):
    print('\033[92m# ' + text + '\033[0m')


def err(text):
    print('\033[91m# ' + text + '\033[0m')


def deb(text):
    if not debug_flag:
        return
    print('\033[90m' + text + '\033[0m')


def run(command):
    deb(command)
    if not dry_run_flag:
        try:
            retcode = subprocess.call(command, shell=True)
            if retcode < 0 or retcode > 0:
                sys.exit(retcode)
        except OSError as e:
            print("Execution failed:", e, file=sys.stderr)


def ssh(server, command):
    cmd = "ssh -t "

    if 'port' in server and server['port'] != '':
        cmd += " -p " + server['port'] + " "

    if 'user' in server and server['user'] != '':
        cmd += server['user'] + "@"

    cmd += server['host'] + " '" + command.replace("'", r"\'") + "'"
    run(cmd)


def upload(server, frm, to, ignore_existing=False):
    cmd = "rsync -chavzP --info=progress2"

    if ignore_existing:
        cmd += " --ignore-existing"

    cmd += " -e 'ssh"

    if 'port' in server and server['port'] != '':
        cmd += " -p " + server['port']

    cmd += "' " + frm + " "

    if 'user' in server and server['user'] != '':
        cmd += server['user'] + "@"

    cmd += server['host'] + ":" + to
    run(cmd)


def archive(destination_dir, path):
    if os.path.isdir(path):
        run("cd %s && tar -zcf %s --totals -C %s ." % (path, destination_dir, path))
    else:
        file = os.path.basename(path)
        path = os.path.dirname(path)
        run("cd %s && tar -zcf %s --totals -C %s %s" % (path, destination_dir, path, file))


def copy_dir(file):
    run("cp -R %s %s" % (file['path'], file['env_path']))


def copy_and_replace(variables, file):
    cmdVars = ""

    if not os.path.exists(os.path.dirname(file['env_path'])):
        run("mkdir -p %s" % os.path.dirname(file['env_path']))

    if 'replace_vars' in file and file['replace_vars'] and len(variables) > 0:
        for var, val in variables.items():
            cmdVars += " -e 's/${%s}/%s/g'" % (var, val.replace('/', '\/'))
        cmd = "cat %s | sed %s > %s" % (file['path'], cmdVars, file['env_path'])
    else:
        cmd = "cp %s %s" % (file['path'], file['env_path'])
    run(cmd)


def replace_variables(variables, str):
    for var, val in variables.items():
        str = str.replace("$" + var, val)
    return str


def find_files_for_replace(path, patterns):
    fileCandidates = []
    for root, subdirs, files in os.walk(path):
        for file in files:
            if not re.findall("(%s)" % "|".join(patterns), file):
                continue
            fileCandidates.append(os.path.join(root, file))

    print(fileCandidates)
    return fileCandidates


def docker_build(variables, container):
    build_variables = variables
    build_variables['DOCKERFILE_DIR'] = os.path.dirname(container['dockerfile'])

    container['name'] = replace_variables(variables, container['name'])
    container['registry'] = replace_variables(variables, container['registry'])
    container['dockerfile'] = os.path.join(config.work_dir, replace_variables(variables, container['dockerfile']))

    build_args = []
    for arg in container['build_args']:
        arg = replace_variables(build_variables, arg)
        build_args.append('--build-arg ' + arg)

    if container['build_path'] == "./":
        container['build_path'] = os.path.dirname(container['dockerfile'])
    else:
        container['build_path'] = os.path.join(config.work_dir, replace_variables(variables, container['build_path']))

    run("docker build %s -t %s/%s -f %s %s" % (
        " ".join(build_args),
        container['registry'],
        container['name'],
        container['dockerfile'],
        container['build_path'],
    ))


def docker_push(variables, container):
    container['registry'] = replace_variables(variables, container['registry'])
    container['name'] = replace_variables(variables, container['name'])
    run("docker push %s/%s" % (
        container['registry'],
        container['name']
    ))


def docker_dump(variables, container):
    container['registry'] = replace_variables(variables, container['registry'])
    container['name'] = replace_variables(variables, container['name'])

    temp_path = config.temp_dir_environment
    if 'deploy_separately' in container and container['deploy_separately']:
        temp_path = config.temp_dir_containers

    run("docker save %s/%s -o %s" % (
        container['registry'],
        container['name'],
        os.path.join(temp_path, replace_variables(variables, container['arch_name']))
    ))


def docker_import(server, variables, container):
    ssh(server, "cd %s && docker load -i %s" % (
        config.destination_dir,
        replace_variables(variables, container['arch_name'])
    ))


def init_server(server, variables, commands):
    for command in commands:
        ssh(server, replace_variables(variables, command))


def stage_cleanup_temp_dir():
    mes("Create / cleanup temp directory")
    run("mkdir -p %s" % config.temp_dir)
    run("rm -rf %s/*" % (config.temp_dir))
    run("mkdir -p %s" % config.temp_dir_environment)
    run("mkdir -p %s" % config.temp_dir_containers)
    run("mkdir -p %s" % config.temp_dir_archives)


def http_request(url):
    (host, path) = url.split('/', 1)
    conn = http.client.HTTPSConnection(host)
    conn.request('GET', '/' + path, None, {'User-agent': 'AirShip'})
    return conn.getresponse().read().decode()
    print(response)


def update():
    resp = http_request('api.github.com/repos/sneakersass/airship/git/refs/tags/')
    tags = json.loads(resp)
    latest_tag_name = tags[len(tags)-1]['ref'].replace('refs/tags/', '')
    current_version = version.replace('v', '').replace('.', '')
    latest_version = latest_tag_name.replace('v', '').replace('.', '')
    if latest_version == current_version or latest_version < current_version:
        mes("Newest version %s is here!" % version)
        exit()

    code = http_request("raw.githubusercontent.com/sneakersass/airship/%s/src/deploy.py" % latest_tag_name)

    if '### END OF CODE' not in code or '### START OF CODE' not in code:
        err("Downloaded code is broken. Check github repository issues or try again.")
        exit()

    ask = input("Newest version is %s. Start update Y/n: " % latest_tag_name)
    if ask != "Y" and ask != "y" and ask != "":
        exit()

    f = open(sys.argv[0], "w")
    f.write(code)
    f.close()

    mes("AirShip updated to %s" % latest_tag_name)


print("AirShip %s takes of...\n%s" % (version, getattr(config, 'motd', '')))

# -- Prepare

commands = []
server_name = ""
commands_str = ""

if commands_str != "":
    commands = commands_str.strip('').split(",")

flags = []

for i, arg in enumerate(sys.argv):
    if arg[0] == "-":
        flags.append(arg)
    elif i > 0 and server_name == "":
        server_name = arg
    elif i > 0 and commands_str == "":
        commands_str = arg

debug_flag = "-v" in flags
dry_run_flag = "--dry" in flags
skip_containers_flag = "--skip-containers" in flags
update_flag = "--update" in flags
version_flag = "--version" in flags

if len(sys.argv) < 2:
    usage()
    exit()

if 'run' in commands or 'deploy' in commands or 'build' in commands or 'init' in commands:
    if len(sys.argv) < 3:
        usage()
        exit()
    if server_name not in config.servers:
        err("Error: server [%s] not exist in config" % server_name)
        exit()

if server_name != '':
    server = config.servers[server_name]

    config.variables.update(
        {
            'SERVER_NAME': server_name,
            'VERSION': server['version'],
            'ENV': server['env'],
        }
    )

    if 'variables' in server:
        config.variables.update(server['variables'])

    if "destination_dir" in server:
        config.destination_dir = server['destination_dir']

config.variables.update(
    {
        'DESTINATION_DIR': config.destination_dir,
        'DOCKER_PROJECT_NAME': config.docker_project_name,
    }
)

if skip_containers_flag:
    config.containers = []

config.temp_dir_environment = os.path.join(config.temp_dir, "environment")
config.temp_dir_containers = os.path.join(config.temp_dir, "containers")
config.temp_dir_archives = os.path.join(config.temp_dir, "archives")


def signal_handler(signal, frame):
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)

if update_flag:
    commands = ['update']

if version_flag:
    commands = ['version']

if len(commands) < 1:
    ask = input("Do you want to build and deploy v%s to [%s] Y/n: " % (server['version'], server_name))
    if ask == "Y" or ask == "y" or ask == "":
        commands = ['build', 'deploy']
    else:
        exit()

# -- Commands

# Version
if 'version' in commands:
    mes("Current version is %s" % version)

# Update
if 'update' in commands:
    mes("Checking for updates...")
    update()

# Build
if 'init' in commands:
    mes("Start initializing server [%s]" % server_name)
    init_server(server, config.variables, config.server_init_commands)

# Build
if 'build' in commands:
    mes("Start building v%s for [%s]" % (server['version'], server_name))

    stage_cleanup_temp_dir()

    mes("Build containers")
    for container in config.containers:
        docker_build(config.variables, container)
        if 'arch_name' not in container:
            docker_push(config.variables, container)

# Deploy
if 'deploy' in commands:
    mes("Start deploy v%s to [%s]" % (server['version'], server_name))

    deb("Variables: %r" % config.variables)

    stage_cleanup_temp_dir()

    mes("Dump containers")
    for container in config.containers:
        if 'arch_name' in container:
            docker_dump(config.variables, container)

    mes("Copy environment files")
    for file in config.files:
        file['path'] = os.path.join(config.work_dir, file['path'])
        file['path'] = replace_variables(config.variables, file['path'])

        file['env_path'] = os.path.join(config.temp_dir_environment, file['env_path'])
        file['env_path'] = replace_variables(config.variables, file['env_path'])

        if not os.path.exists(file['path']):
            err("File/dir %s not exist" % file['path'])
            continue

        if os.path.isfile(file['path']):
            # @TODO mkdir?
            copy_and_replace(config.variables, file)

        if os.path.isdir(file['path']):
            copy_dir(file)

            if 'replace_vars' in file and file['replace_vars']:
                for dirFile in find_files_for_replace(file['path'], config.replace_vars_file_patterns):
                    copy_and_replace(
                        config.variables,
                        {
                            'path': dirFile,
                            'replace_vars': True,
                            'env_path': os.path.join(config.temp_dir_environment, file['env_path'],
                                                     os.path.relpath(dirFile, file['path']))
                        }
                    )

    mes("Build archive(s)")
    archive(os.path.join(config.temp_dir_archives, config.arch_name), config.temp_dir_environment)

    mes("Create destination dir [%s] on destination server" % config.destination_dir)
    ssh(server, "mkdir -p %s" % config.destination_dir)

    mes("Upload archive")
    upload(server, "%s/*" % config.temp_dir_archives, "%s/" % config.destination_dir)

    mes("Extract archive")
    ssh(server, "cd %s && tar -xzf %s --totals ." % (config.destination_dir, config.arch_name))

    for container in config.containers:
        if 'arch_name' in container:
            temp_path = config.temp_dir_environment
            if 'deploy_separately' in container and 'deploy_separately' in container and container['deploy_separately']:
                temp_path = config.temp_dir_containers

                temp_path = os.path.join(temp_path, replace_variables(config.variables, container['arch_name']))

                excludeVariables = {}
                for var, val in config.variables.items():
                    excludeVariables[var] = "*[^" + val + "]"

                if 'remove_old' in container and container['remove_old']:
                    ssh(server, "rm -f " + os.path.join(config.destination_dir,
                                                        replace_variables(excludeVariables, container['arch_name'])))

                upload(server, temp_path, config.destination_dir,
                       'ignore_existing' in container and container['ignore_existing'])
            docker_import(server, config.variables, container)

    mes("Run")
    ssh(server, replace_variables(config.variables, config.run_command))

# Run
if 'run' in commands:
    mes("Run")
    ssh(server, replace_variables(config.variables, config.run_command))

### END OF CODE