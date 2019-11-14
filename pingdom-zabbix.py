#!/usr/bin/env python

#
# modules
#
import json
import re
import requests
import subprocess
from configparser import ConfigParser

#
# pull in the config
#
config = ConfigParser()
config.read('pingdom-zabbix.ini')

#
# zabbix trapper call
#
def zabbix_trapper(cmd_args):
    try:
        print(' '.join(cmd_args))
        print(subprocess.check_output(cmd_args))
    except subprocess.CalledProcessError as e:
        print("EXCEPTION")
        print("returncode:", e.returncode)
        print("cmd:", e.cmd)
        print("output:", e.output)

#
# pull pingdom data (checks and values)
#
def pingdom_data(pingdom_response):
    data = []
    for check in pingdom_response.json()['checks']:
        data.append({
            'name': check['name'],
            'status': check['status'],
            'resptime': check['lastresponsetime']
        })
    return data

#
# pull statuscake data (checks and values)
#
def statuscake_data(statuscake_response):
    data = []
    for check in statuscake_response.json():
        status = check['Status'].lower()
        if check['Paused'] == True:
            status = "paused"
        data.append({
            'name': check['WebsiteName'],
            'status': status
        })
    return data

#
# pingdom checks -> zabbix discovery
#
def zabbix_discovery(data):
    discovery = []
    for check in data:
        discovery.append(
            {"{#NAME}": str(check['name'])}
        )
    cmd_args = [
        'zabbix_sender',
        '-z', config.get('ZABBIX', 'server'),
        '-p', config.get('ZABBIX', 'port'),
        '-s', config.get('ZABBIX', 'host'),
        '-k', config.get('ZABBIX', 'key1'),
        '-o', json.dumps({ 'data': discovery })
    ]
    zabbix_trapper(cmd_args)

#
# pingdom status -> zabbix trapper
#
def zabbix_status(data):
    for check in data:
        # turn 'up' into 1 and 'down' into 0
        status = 0
        if check['status'] == 'up':
            status = 1
        cmd_args = [
            'zabbix_sender',
            '-z', config.get('ZABBIX', 'server'),
            '-p', config.get('ZABBIX', 'port'),
            '-s', config.get('ZABBIX', 'host'),
            '-k', config.get('ZABBIX', 'key2') + '[' + str(check['name']) + ']',
            '-o', str(status)
        ]
        zabbix_trapper(cmd_args)

#
# pingdom lastresponsetime -> zabbix trapper
#
def zabbix_resptime(data):
    for check in data:
        cmd_args = [
            'zabbix_sender',
            '-z', config.get('ZABBIX', 'server'),
            '-p', config.get('ZABBIX', 'port'),
            '-s', config.get('ZABBIX', 'host'),
            '-k', config.get('ZABBIX', 'key3') + '[' + str(check['name']) + ']',
            '-o', str(check['resptime'])
        ]
        zabbix_trapper(cmd_args)

def fetch_pingdom():
    # pingdom variables (convenience)
    pingdom = dict(
        apiurl   = config.get('PINGDOM', 'apiurl'),
        appkey   = config.get('PINGDOM', 'appkey'),
        username = config.get('PINGDOM', 'username'),
        password = config.get('PINGDOM', 'password')
    )
    # connect to pingdom
    res = requests.get(pingdom['apiurl'], auth=(pingdom['username'],pingdom['password']), headers={'App-Key': pingdom['appkey']})
    if res.status_code == requests.codes.ok:
        # fetch pingdom data (checks and values)
        data = pingdom_data(res)
        # pingdom checks -> zabbix discovery
        zabbix_discovery(data)
        # pingdom status and lastresponsetime -> zabbix values
        zabbix_status(data)
        zabbix_resptime(data)
    else:
        print("EXCEPTION: Bad Request; HTTP {}".format(str(res.status_code)))

def fetch_statuscake():
    # statuscake variables (convenience)
    statuscake = dict(
        apiurl   = config.get('STATUSCAKE', 'apiurl'),
        apikey   = config.get('STATUSCAKE', 'apikey'),
        username = config.get('STATUSCAKE', 'username'),
    )
    # connect to statuscake
    res = requests.get(statuscake['apiurl'], headers={'API': statuscake['apikey'], 'Username': statuscake['username']})
    if res.status_code == requests.codes.ok:
        # fetch statuscake data (checks and values)
        data = statuscake_data(res)
        # statuscake checks -> zabbix discovery
        zabbix_discovery(data)
        # statuscake status -> zabbix values
        zabbix_status(data)
    else:
        print("EXCEPTION: Bad Request; HTTP {}".format(str(res.status_code)))


try:
    if 'PINGDOM' in config:
        fetch_pingdom()
    elif 'STATUSCAKE' in config:
        fetch_statuscake()
    else:
        print("EXCEPTION: Neither PINGDOM nor STATUSCAKE section found in config!")

except Exception as e:
    print("EXCEPTION: {} in line {}".format(str(e)))
