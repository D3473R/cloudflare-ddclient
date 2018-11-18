#!/usr/bin/python

import argparse
import json
import logging as log
import os
import sys
import time

import daemon
import requests

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
DAEMONIZE = False

ZONE_ID = None
RECORD_ID = None

log.basicConfig(
    filename=os.path.join(SCRIPT_PATH, 'ddclient-cloudflare.log'),
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=log.DEBUG
)

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(help='commands', dest="command")

parser_start = subparsers.add_parser('start', help='starts the ddclient')
parser_stop = subparsers.add_parser('stop', help='stops the ddclient')

parser_start.add_argument('domain', help='your cloudflare domain: e.g. example.com')
parser_start.add_argument('subdomain', help='your cloudflare subdomain: e.g. sub.example.com')
parser_start.add_argument('--daemon', '-d', default=False, action='store_true', dest='daemon',
                          help='start the ddclient as a daemon')

args = parser.parse_args()

if args.command == 'start':
    if args.daemon:
        DAEMONIZE = True
    if args.domain and args.subdomain:
        pass
    else:
        exit()
elif args.command == 'stop':
    try:
        pid_file = open('/tmp/ddclient.py.pid', 'r')
        pid = pid_file.read(100)
        pid_file.close()
        print('Killing process %s' % pid)
        log.debug('Killing process %s' % pid)
        os.system('kill %s' % pid)
    except:
        pass
    exit()
else:
    exit()

try:
    settings = open(os.path.join(SCRIPT_PATH, 'settings.json'), 'r')
    settings_obj = json.load(settings)
except Exception as e:
    print('Error : settings.json file not found')
    exit()

###############################
# Defined in settings.json
# CF_EMAIL = 'email@example.com'
# CF_API_KEY = 'yourapikey'
##############################

CF_EMAIL = settings_obj['CF_EMAIL']
CF_API_KEY = settings_obj['CF_API_KEY']
HEADERS = {'X-Auth-Key': CF_API_KEY, 'X-Auth-Email': CF_EMAIL, 'Content-Type': 'application/json'}

SLEEP_INTERVAL_SEC = 300
CF_DOMAIN = args.domain
CF_SUB_DOMAIN = args.subdomain
CF_URL = 'https://api.cloudflare.com/client/v4/'
ZONE_ID_FILEPATH = '/tmp/ddclient.zoneid_{}'.format(
    CF_DOMAIN
)
RECORD_ID_FILEPATH = '/tmp/ddclient.recid_{}_{}'.format(
    CF_DOMAIN, CF_SUB_DOMAIN
)


def get_ip():
    try:
        response_text = requests.get('https://ipinfo.io/ip').text
        ipaddr = response_text.strip('\n')
        return ipaddr
    except:
        log.debug('Error: Cannot resolve IP address!')
        print('Error : Cannot resolve IP address!')
        pass


def get_zone_id():
    zone_id = ''
    try:
        with open(ZONE_ID_FILEPATH, 'r') as f:
            zone_id = f.read()
            # return zone_id.strip()
    except:
        pass

    try:
        data = {'name': CF_DOMAIN, 'status': 'active', 'order': 'status', 'direction': 'desc'}
        response_text = requests.get(CF_URL + 'zones?', params=data, headers=HEADERS).text

    except:
        log.debug('Eror : Cannot open socket!')
        print('Error : Cannot open socket!')
        sys.exit(1)

    response = json.loads(response_text)

    flag_found_name = False
    for result in response['result']:
        if result['name'] == CF_DOMAIN:
            flag_found_name = True
            zone_id = result['id']
            break

    if flag_found_name:
        try:
            with open(ZONE_ID_FILEPATH, 'w') as f:
                f.write(zone_id)
            return (zone_id)
        except:
            print('Error : I/O error, cannot open files!')
            sys.exit(1)
    else:
        log.debug('Error : Unable to find domain!')
        print('Error : Unable to find domain!')


def get_record_id():
    rec_id = ''
    try:
        with open(RECORD_ID_FILEPATH, 'r') as f:
            rec_id = f.read()
            # return rec_id.strip()
    except:
        pass

    try:

        data = {'type': 'A', 'name': CF_SUB_DOMAIN, 'order': 'name', 'direction': 'desc'}
        response_text = requests.get(CF_URL + 'zones/' + ZONE_ID + '/dns_records', params=data, headers=HEADERS).text

    except:
        log.debug('Error : Cannot open socket!')
        print('Error : Cannot open socket!')
        sys.exit(1)

    response = json.loads(response_text)

    flag_found_name = False
    for result in response['result']:
        if result['name'] == CF_SUB_DOMAIN:
            flag_found_name = True
            rec_id = result['id']

    if flag_found_name:
        try:
            with open(RECORD_ID_FILEPATH, 'w') as f:
                f.write(rec_id)
            return rec_id
        except:
            print('Error : I/O error, cannot open files!')
            sys.exit(1)
    else:
        log.debug('Error : Unable to find sub domain or domain!')
        print('Error : Unable to find sub domain or domain!')
        pass


def update_record():
    if ZONE_ID and RECORD_ID:
        my_ip = get_ip()

        try:
            with open('/tmp/ddclient.py.ipaddr', 'r') as f:
                ip = f.read().strip()
            if my_ip == ip:
                return
        except:
            pass

        try:
            data = {'type': 'A', 'name': CF_SUB_DOMAIN, 'content': my_ip}
            response_text = requests.put(CF_URL + 'zones/' + ZONE_ID + '/dns_records/' + RECORD_ID,
                                         data=json.dumps(data), headers=HEADERS).text
        except:
            print('Error : Cannot open socket!')
            sys.exit(1)

        response = json.loads(response_text)
        if response['success']:
            file = open('/tmp/ddclient.py.ipaddr', 'w')
            file.write(my_ip)
            log.debug('IP Updated' + str(my_ip))
            file.close()
        else:
            log.debug('Error : Was unable to update. Cause : {}'.format(response['messages']))
            print('Error : Was unable to update.')
            print('Cause : %s' % response['messages'])
            sys.exit(1)

    else:
        log.debug('Error : Unable to find provided sub domain.')
        print('Error : Unable to find provided sub domain.')
        sys.exit(1)


def write_pid(pid):
    pid_file = open('/tmp/ddclient.py.pid', 'w')
    pid_file.write(str(pid))
    pid_file.close()
    return


def daemonize():
    with daemon.DaemonContext():
        write_pid(os.getpid())
        while True:
            update_record()
            time.sleep(SLEEP_INTERVAL_SEC)


if __name__ == '__main__':
    ZONE_ID = get_zone_id()
    RECORD_ID = get_record_id()
    update_record()
    if DAEMONIZE:
        daemonize()
