#!/usr/env/python

import re
import json
import yaml
import pprint

# Copyright 2017 Nokia
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

def ipfabric_wbxPort_to_portIndex(sros_port):
    '''
    Input (string) SROS/TiMOS port '1/1/1'
    Output (integer) value between 0-127
    ''' 
    card = int(sros_port.split('/')[0])
    mda = int(sros_port.split('/')[1])
    port_id = int(sros_port.split('/')[2])
    index = ((mda - 1)*64)+(port_id-1)%64
    return index

def ipfabric_portIndex_to_wbxPort(index):
    '''
    Input (integer) value between 0-127
    Output (string) SROS/TiMOS port '1/1/1'
    '''
    card = int(1)
    mda = int(index//64)+1
    port_id = int((index%64)+1)
    port = '{}/{}/{}'.format(card,mda,port_id)
    return port

def ipfabric_ethosPort_to_portIndex(port):
    '''
    Input (string) ETHOS port 'ethernet-1/1'
    Output (integer) value between 0-127
    ''' 
    p = port.replace('ethernet-', '')
    print(p)
    card = int(p.split('/')[0])
    mda = 1
    port_id = int(p.split('/')[1])
    index = ((mda - 1)*64)+(port_id-1)%64
    return index

def ipfabric_portIndex_to_ethosPort(index):
    '''
    Input (integer) value between 0-127
    Output (string) SROS/TiMOS port '1/1/1'
    '''
    card = int(1)
    mda = int(index//64)+1
    port_id = int((index%64)+1)
    #port = '{}/{}/{}'.format(card,mda,port_id)
    port = 'ethernet-' + str(card) + '/' + str(port_id)
    return port

    
def integer_to_anycast_mac(value):
    '''
    Input (integer) value (48-bit) of a mac address)
    Output (string) regular mac address
    '''
    macaddr_hex = format(value, '012x')
    macaddr_string = ':'.join(s.encode('hex') for s in macaddr_hex.decode('hex'))
    return macaddr_string

def ipfabric_generate_port_range(build_vars):
    '''
    Expects a dict as input: {'media_mode': '100G', 'port_range':{'start': '1/1/1', 'end': '1/1/13'}}
    Converts SROS/TiMOS ports to regular integer values, depending on hardware.
    Output (list of integers): [0,4,8,12]
    '''
    port_list = []
    media_mode = build_vars['media_mode']
    if media_mode in ("100G", "40G"):
        step=4
    elif media_mode in ("2x50G"):
        step=2
    elif media_mode in ("4x25G", "4x10G"):
        step=1
    elif media_mode in ("veth"):
        step=1
    for port_range in build_vars['port_range']:
        start_index = ipfabric_ethosPort_to_portIndex(port_range['start'])
        end_index = ipfabric_ethosPort_to_portIndex(port_range['end'])
        for port in xrange(start_index, end_index+1, step):
            port_list.append(port)
    port_list.sort()
    #print("PortList: ", port_list)
    return port_list

def ipfabric_portindexlist_to_SROS_list(port_list):
    port_list.sort()
    sros_port_list = [ipfabric_portIndex_to_wbxPort(i) for i in port_list]
    return sros_port_list

def ipfabric_portindexlist_to_ETHOS_list(port_list):
    port_list.sort()
    sros_port_list = [ipfabric_portIndex_to_ethosPort(i) for i in port_list]
    return sros_port_list

def ipfabric_build_vars(build_vars):
    '''
    '''
    autofabric = {}
    # Expand port_ranges
    build_vars['leaf']['uplink']['port_list'] = ipfabric_generate_port_range(build_vars['leaf']['uplink'])
    build_vars['spine']['downlink']['port_list'] = ipfabric_generate_port_range(build_vars['spine']['downlink'])

    # Generate Spine configuration
    spine_count = build_vars['spine']['amount']
    leaf_uplink_count = len(build_vars['leaf']['uplink']['port_list'])
    spine_downlink_count = len(build_vars['spine']['downlink']['port_list'])
    spine_ports_per_leaf = leaf_uplink_count / spine_count
    
    autofabric['leafs'] = []
    for leafid in xrange(0,build_vars['leaf']['amount']):
        device={}
        device['nodeid'] = leafid
        device['hostname'] = build_vars['leaf']['hostname']+str(leafid+1)
        device['port_list'] = {}
        for index,port in enumerate(build_vars['leaf']['uplink']['port_list']):
            spineid = index%int(leaf_uplink_count/spine_ports_per_leaf)
            interfaceindex = int(index/spine_ports_per_leaf)%spine_ports_per_leaf
            device['port_list'][port] = {}
            device['port_list'][port]['spineid'] = spineid+1
            device['port_list'][port]['intindex'] = interfaceindex+1
            device['port_list'][port]['remote'] = build_vars['spine']['downlink']['port_list'][(interfaceindex*spine_downlink_count/spine_ports_per_leaf)+leafid]
        autofabric['leafs'].append(device)

    autofabric['spines'] = []
    for spineid in xrange(0,build_vars['spine']['amount']):
        device = {}
        device['nodeid'] = spineid
        device['hostname'] = build_vars['spine']['hostname']+str(spineid+1)
        device['port_list'] = {}
        for index,port in enumerate(build_vars['spine']['downlink']['port_list']):
            leafid = index%int(spine_downlink_count/spine_ports_per_leaf)
            interfaceindex = int(index/(spine_downlink_count/spine_ports_per_leaf))
            device['port_list'][port] = {}
            device['port_list'][port]['leafid'] = leafid+1
            device['port_list'][port]['intindex'] = interfaceindex+1
            device['port_list'][port]['remote'] = build_vars['leaf']['uplink']['port_list'][interfaceindex*(leaf_uplink_count/spine_ports_per_leaf)+spineid]
        autofabric['spines'].append(device)

    autofabric['input'] = build_vars
    return autofabric


if __name__ == '__main__':
    with open("/Users/henderiw/ansible/fabric-builder-ethos/build_vars.yml", 'r') as stream:
        try:
            #print(yaml.safe_load(stream))
            data = yaml.safe_load(stream)
            pp = pprint.PrettyPrinter(indent=4)
            #pp.pprint(data['ipfabric']['leaf'])
            a = ipfabric_build_vars(data['ipfabric'])
            pp.pprint(a)
            p = ipfabric_portIndex_to_ethosPort(1)
            pp.pprint(p)
        except yaml.YAMLError as exc:
            print(exc)
