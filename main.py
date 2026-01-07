
from dataclasses import dataclass
import json


SUPPORTED_IGP = {"OSPF", "RIP"}

@dataclass
class Interface:
    ipv6: str
    ngbr: str

@dataclass
class Router:
    name : str
    interfaces : dict[str,Interface]

@dataclass
class AS:
    asn : str
    igp : str
    routers : dict[str, Router]

@dataclass
class Inventory:
    ases : dict[int, AS]
    router_to_as : dict[str, int]

def load_file(path):
    with open(path) as f:
        data = json.load(f)
    return data


def parse_info(path):
    data = load_file(path)
    
    if not isinstance(data, dict) or "AS" not in data:
        raise ValueError("No AS information in the json file")
    as_raw = data["AS"]

    if not isinstance(as_raw, dict) or not as_raw:
        raise ValueError("Empty AS")
    
    ases: dict[int, AS]={}
    router_to_as: dict[str, int]={}

    for asn_str, as_body in as_raw.items():
        as_number = int(asn_str)
        if as_number in ases:
            raise ValueError(f"AS {as_number} present more than one time in the set")
        igp = str(as_body.get("igp", "")).upper().strip()


        if igp not in SUPPORTED_IGP:
            raise ValueError(f"{igp} not supported in this project, choose from this list : {SUPPORTED_IGP}")
        
        routers_raw = as_body.get("routers")
        if not routers_raw or not isinstance(routers_raw, dict):
            raise ValueError(f"AS {as_number} has no routers, or verify the syntax of dict structures in python")
        
        routers : dict[str, Router]={}

        for router_name, router_body in routers_raw.items():
            if router_name in router_to_as:
                raise ValueError(f"Router {router_name} is present in different ASes")
            
            int_raw = router_body.get("interfaces")
            interfaces : dict[str, Interface]={}

            for int_name, int_body in int_raw.items():
                ipv6 = str(int_body.get("ipv6", ""))
                ngbr = str(int_body.get("ngbr", ""))

                if not ngbr:
                    raise ValueError(f"Router {router_name} is isolated :( )")

                interfaces[int_name] = Interface(ipv6=ipv6, ngbr=ngbr)
            routers[router_name] = Router(name = router_name, interfaces=interfaces)
            router_to_as[router_name] = as_number
        ases[as_number] = AS(asn = as_number, igp =igp, routers = routers)
    return Inventory(ases = ases, router_to_as=router_to_as)


def basic_validation(path):
    inventory = parse_info(path)

    for asn, as_body in inventory.ases.items():
        for router_name, router_body in as_body.routers.items():
            for interface_name, interface_body in router_body.interfaces.items():
                if interface_body.ngbr not in inventory.router_to_as:
                    raise ValueError(f"{router_name}:{interface_name} neighbor {interface_body.ngbr!r} not found in inventory")
                
    for asn, as_body in inventory.ases.items():
        for router_name, router_body in as_body.routers.items():
            for interface_name, interface_body in router_body.interfaces.items():
                neighbor = interface_body.ngbr
                nasn = inventory.router_to_as[neighbor]
                nrouter = inventory.ases[nasn].routers[neighbor]
                long = 0
                for a,b in nrouter.interfaces.items():
                    if b.ngbr == router_name:
                        long+=1
                if long==0:
                    raise ValueError(f"Link not reciprocal in {router_name}, {interface_name}")
                if long>1:
                    raise ValueError(f"Multiple interfaces pointing to {router_name}")
    return inventory
        
def internal_interfaces(inv, asn):
    as_obj = inv.ases[asn]
    internal: dict[str, set[str]] = {router_name: set() for router_name in as_obj.routers.keys()}

    for router_name, router_body in as_obj.routers.items():
        for interface_name, interface_body in router_body.interfaces.items():
            neighbor = interface_body.ngbr
            if neighbor in inv.router_to_as and inv.router_to_as[neighbor] == asn:
                internal[router_name].add(interface_name)
    return internal


def rip_commands(inv, asn):
    as_obj = inv.ases[asn]
    internal = internal_interfaces(inv, asn)
    rip_name = f"AS{asn}"
    out: dict[str, list[str]]={}

    for router_name, router_body in as_obj.routers.items():
        cmds: list[str]= []
        cmds += ["conf t", "ipv6 unicast-routing"]
        cmds+= [f"ipv6 router rip {rip_name}"]
        for interface_name in sorted(internal[router_name]):
            cmds+= [f"int {interface_name}", f"ipv6 enable", f"ipv6 rip {rip_name} enable", "no shutdown", "exit"]
        cmds += ["end", "write mem"]
        out[router_name]=cmds
    return out


def ospf_commands(inv, asn):
    as_obj = inv.ases[asn]
    internal = internal_interfaces(inv, asn)
    out: dict[str, list[str]]={}
    X=1
    for router_name, router_body in as_obj.routers.items():
        print(router_body)
        cmds: list[str]= []
        cmds += ["conf t", "ipv6 unicast-routing"]
        cmds+= [f"ipv6 router ospf {asn}"]
        cmds+= [f"router-id 10.10.10.{X}"]
        X+=1
        for interface_name in sorted(internal[router_name]):
            cmds+= [f"int {interface_name}", f"ipv6 enable", f"ipv6 ospf {asn} area 0", "no shutdown", "exit"]
        cmds += ["end", "write mem"]
        out[router_name]=cmds
    return out


    
path1 = "/home/kali/Desktop/gns_pro/config.json"
path2 = "/home/kali/Desktop/gns_pro/config_vide.json"


inv = parse_info(path1)
print(inv)
commands_rip = rip_commands(inv, 101)
commands_ospf = ospf_commands(inv, 101)
print(commands_ospf)
