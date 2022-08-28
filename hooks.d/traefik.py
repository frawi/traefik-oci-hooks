#!/usr/bin/python3

import json
import os
import subprocess
import sys
import time
import yaml

TRAEFIK_DYNAMIC = "/srv/traefik/dynamic"
PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
#sys.stdout = sys.stderr = open("/tmp/traefik.log", "w")

def decode_labels(labels):
    conf = {}
    for name, value in labels.items():
        if not name.startswith("traefik."):
            continue

        d = conf
        _, *path, key = name.split(".")
        for p in path:
            if p[-1] == ']':
                s = p.index("[")
                if s > 0:
                    if not p[:s] in d:
                        d[p[:s]] = {}

                    d = d[p[:s]]
                    p = p[s+1:-2]

            if not p in d or d[p] == 'true':
                d[p] = {}

            d = d[p]

        d[key] = value

    del conf['enable']
    return conf

def default_service(spec):
    bindings = spec["NetworkSettings"]["Ports"]
    bind, *_ = bindings.values()
    port = bind[0]["HostPort"]
    return dict(loadbalancer=dict(server=dict(port=port)))

def apply_defaults(conf, spec):
    nw, *_ = spec['NetworkSettings']['Networks'].values()
    server = nw["Gateway"]

    for proto_name, proto in conf.items():
        if not proto['routers']:
            continue

        routers = proto['routers']
        services = proto['services'] = proto.get('services', {})

        if len(routers) == 1:
            # if there is only one router, we can infer the config
            (router_name, router), = routers.items()
            if not 'service' in routers:
                if len(services) == 1:
                    # if there is a service, we just use that
                    service_name, = services
                    router['service'] = service_name
                elif len(services) == 0:
                    # if there is no service, we create a default
                    router['service'] = router_name
                    services[router_name] = default_service(spec)

        for route in routers.values():
            if 'entrypoints' in route:
                # split entrypoints at ','
                route['entrypoints'] = [e.strip() for e in route['entrypoints'].split(',')]

            if 'middlewares' in route:
                # split middlewares at ','
                route['middlewares'] = [m.strip() for m in route['middlewares'].split(',')]

            if 'tls' in route:
                # transform domains dict to array
                domains = []
                tls = {}
                for key, val in route['tls'].items():
                    if key.startswith('domains[') and key[-1] == ']':
                        if 'sans' in val:
                            val['sans'] = [s.strip() for s in route['sans'].split(',')]
                        domains.append(val)
                    else:
                        tls[key] = val
                tls['domains'] = domains
                route['tls'] = tls


        for service in services.values():
            loadbalancer = service.get('loadbalancer')
            if loadbalancer:
                servers = loadbalancer['servers'] = []
                if 'server' in loadbalancer:
                    port = loadbalancer['server']['port']
                    if proto_name == 'http':
                        scheme = loadbalancer['server'].get('scheme', 'http')
                        url = f"{scheme}://{server}:{port}"
                        servers.append(dict(url=url))
                    else:
                        servers.append(dict(address=f"{server}:{port}"))

                    del loadbalancer['server']

def main():
    data = json.load(sys.stdin)
    cid = data["id"]
    filename = f"{TRAEFIK_DYNAMIC}/{cid}.yaml"

    if data["status"] == "stopped":
        if os.path.exists(filename):
            os.remove(filename)
        return

    if os.fork() != 0:
        return

    with subprocess.Popen(["/usr/bin/podman", "inspect", cid], stdout=subprocess.PIPE, env=dict(PATH=PATH)) as proc:
        spec = json.load(proc.stdout)[0]

    if not spec["Config"]["Labels"].get("traefik.enable", False):
        return

    conf = decode_labels(spec["Config"]["Labels"])
    apply_defaults(conf, spec)

    with open(filename, "w") as fp:
        yaml.dump(conf, fp)

if __name__ == '__main__':
    main()
