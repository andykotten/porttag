import sys
import re
from ncclient import manager
from ncclient import operations
from ncclient import transport

''' Script to tag ports in requested VLAN '''

def get_element(xml_line):
    "Returns the value between the <xml></xml> tags"
    return re.search(r'(>)(.*)(<)', xml_line).group(2)

def port_location(ports):
    "Strip the port location field into list of switch serial # and port #"
    return re.findall(r'([A-Z]{3}\w{8})[^\w]+(\d+)', ports)

def vlan_check(username, password, ip, vlan):
    "Check if the vlan want to change to is available and not a restricted one"

    if (vlan == "1") or (vlan == "900") or (vlan == "901") or (vlan == "912") or (vlan == "950"):
        return -1
    try:
        with manager.connect(host=ip,
                             port=22,
                             username=username,
                             password=password,
                             hostkey_verify=False,
                             device_params={'name': 'nexus'},
                             allow_agent=False,
                             look_for_keys=False
                             ) as cisco_manager_core:

            showcommand = {"show vlan id %s" % vlan}
            try:
                output = cisco_manager_core.exec_command(showcommand)
            except operations.RPCError:
                return -1

            if output.xml.find("active") != -1:
                return 0
            else:
                return -1

    except transport.AuthenticationError:
        return -2

def tag_port(username, password, ip, vlan, port):
    "Locates the port to tag and tags it"

    with manager.connect(host=ip,
                         port=22,
                         username=username,
                         password=password,
                         hostkey_verify=False,
                         device_params={'name': 'nexus'},
                         allow_agent=False,
                         look_for_keys=False
                         ) as cisco_manager_core:

        showcommand = {"show cdp neighbors"}
        output = cisco_manager_core.exec_command(showcommand)
        alldistros = re.findall(r'(\w+-d(?:1|2).*\.neteng\.ask\.com)', output.xml)

    commandsran = ""
    for line in alldistros:
        with manager.connect(host=line,
                         port=22,
                         username=username,
                         password=password,
                         hostkey_verify=False,
                         device_params={'name': 'nexus'},
                         allow_agent=False,
                         look_for_keys=False
                         ) as cisco_manager_distro:

            showcommand = {"show fex"}
            output = cisco_manager_distro.exec_command(showcommand)
            output2 = re.search(r'%s' % port[0], output.xml)
            if output2 != None:

                for line2 in output.xml.splitlines():
                    if 'fex_number' in line2:
                        fex = get_element(line2)
                    if 'chas_ser' in line2 and port[0] in line2:
                        break

                showcommand={"show run int eth %s/1/%s" % (fex, port[1])}
                output = cisco_manager_distro.exec_command(showcommand)
                commandsran += "BEFORE: " + line + output.xml + '\n'

                confcommand={"configure terminal ; int eth %s/1/%s ; no switchport trunk allowed vlan ; switchport access vlan %s" % (fex, port[1], vlan)}
                cisco_manager_distro.exec_command(confcommand)
                commandsran += "COMMANDS RAN: " + line + '#' + str(confcommand) + '\n'

                showcommand={"show run int eth %s/1/%s" % (fex, port[1])}
                output = cisco_manager_distro.exec_command(showcommand)
                commandsran += "AFTER: " + line + output.xml + '\n'

                if line.find("-d2") != -1:
                    commandsran += "\n===============================================================================\n"
                    return commandsran

    return ""          #default return if no match


def main(username, password, datacenter, vlan, ports):

    commandsran = ""
    if datacenter.strip().upper() == "IAD":
        ip = "10.1.1.1"
    elif datacenter.strip().upper() == "LAS":
        ip = "10.7.1.1"
    else:
       return "That's not a datacenter."

    ports = port_location(ports)
    if ports == []:
        return "Ports not listed in correct format. Put one per line and include switch's serial number."

    vcheck = vlan_check(username, password, ip, vlan)
    if vcheck == -1:          #check if vlan requested is available and not restricted one
        return "Cannot do that vlan."
    elif vcheck == -2:          #check auth credentials
        return "Cannot connect with your credentials."

    for line in ports:
        commandsran += tag_port(username, password, ip, vlan, line)

    if commandsran == "":
        commandsran = "Could not locate those ports."

    return commandsran

if __name__ == "__main__":
    main()
