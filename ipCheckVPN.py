import socket
import json
import os
import re
import smtplib
import subprocess
import psutil
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from time import asctime

# 获取当前文件夹
run_path = os.getcwd()
temp_ip_json_path = os.path.join(run_path, 'temp_ip.json')

# route print 里 VPN 网卡的名字关键字（多个，任一命中即可）
VPN_NAME_KEYWORDS = ['Sangfor', 'VPN', 'EasyConnect']

# 物理网卡名关键字（用于兜底识别物理 IP）
PHYSICAL_KEYWORDS = ['Wi-Fi', 'WLAN', 'Intel', 'Realtek', 'Ethernet', '以太网']

# 明显要排除的虚拟/无关网卡关键字
VIRTUAL_EXCLUDE = [
    'Sangfor', 'SSL VPN', 'EasyConnect', '深信服',
    'TAP-Windows', 'TAP-Win32', 'Netease', 'UU',
    'Hyper-V', 'Virtual', 'VMware', 'VirtualBox',
    'Loopback', 'Bluetooth', '本地连接*', 'Wi-Fi Direct', 'cfw-tap',
]


# ============================ 邮件 ============================

def send_an_email(email_content):
    mail_host = 'smtp.163.com'
    mail_user = '15151056689@163.com'
    mail_auth_code = os.environ.get('MAIL_AUTH_CODE', 'DPQHJMRBFSJPXXQI')
    mail_sender = 'wupeihao974@163.com'
    mail_receivers = ['2119049154@qq.com']

    message = MIMEMultipart()
    message['From'] = Header(mail_sender)
    message['Subject'] = Header("PC(HP_Pavilion)-IP-Report")
    message.attach(MIMEText(asctime(), 'plain', 'utf-8'))
    message.attach(MIMEText(email_content, 'plain', 'utf-8'))

    smtpObj = smtplib.SMTP(mail_host)
    smtpObj.login(mail_user, mail_auth_code)
    smtpObj.sendmail(mail_sender, mail_receivers, message.as_string())
    print("Email sent.")


# ============================ IP 变化检测 ============================

def get_temp_ip(current_ip):
    if not os.path.exists(temp_ip_json_path):
        print("No {}, dump it.".format(temp_ip_json_path))
        with open(temp_ip_json_path, 'w') as jo:
            json.dump(current_ip, jo, ensure_ascii=False)
        return True, current_ip
    else:
        with open(temp_ip_json_path, 'r') as jo:
            origin_ip = json.load(jo)
        if origin_ip == current_ip:
            print("IP do not change, no need to send.")
            return False, current_ip
        else:
            print("IP changed:\n  old = {}\n  new = {}".format(origin_ip, current_ip))
            with open(temp_ip_json_path, 'w') as jo:
                json.dump(current_ip, jo, ensure_ascii=False)
            return True, current_ip


# ============================ 从 route print 拿 VPN MAC（支持多关键字） ============================

def normalize_mac(mac):
    """统一 MAC 格式为 00-FF-6D-69-2D-D1"""
    if not mac:
        return ''
    return mac.replace(':', '-').replace('.', '-').upper()


def get_vpn_macs_from_route(keywords=VPN_NAME_KEYWORDS):
    """
    从 `route print` 的接口列表中提取所有匹配关键字的网卡。
    典型行：
      13...00 ff 6d 69 2d d1 ......Sangfor SSL VPN CS Support System VNIC
    返回列表：[{'keyword': 'Sangfor', 'mac': '00-FF-6D-69-2D-D1', 'desc': '...'}, ...]
    """
    result = []
    try:
        out = subprocess.check_output(
            ['route', 'print'], encoding='gbk', errors='ignore'
        )
    except Exception as e:
        print("route print failed:", e)
        return result

    # 匹配： 数字...MAC(6组两字符，分隔符 空格/-/:) ......描述
    pattern = re.compile(
        r'(\d+)\.\.\.\s*([\da-fA-F]{2}(?:[\s\-:][\da-fA-F]{2}){5})\s*\.\.\.\.\.\.\s*(.*)',
        re.IGNORECASE
    )

    for line in out.splitlines():
        m = pattern.search(line)
        if not m:
            continue
        _, mac_raw, desc = m.groups()
        desc = desc.strip()
        for kw in keywords:
            if kw.lower() in desc.lower():
                result.append({
                    'keyword': kw,
                    'mac': normalize_mac(mac_raw.strip().replace(' ', '-')),
                    'desc': desc,
                })
                break  # 一行只记一次，命中第一个关键字就够
    return result


# ============================ 用 MAC 反查 IPv4 ============================

def get_ip_by_mac(target_mac):
    """
    在 psutil 的网卡列表里，按 MAC 反查 IPv4。
    返回 (iface_name, ipv4) 或 (None, None)
    """
    target = normalize_mac(target_mac)
    if not target:
        return None, None

    for iface, addrs in psutil.net_if_addrs().items():
        macs = [
            normalize_mac(a.address) for a in addrs
            if a.family == psutil.AF_LINK
        ]
        if target not in macs:
            continue
        for a in addrs:
            if a.family == socket.AF_INET and not a.address.startswith('127.'):
                if a.address.startswith('169.254.'):
                    continue  # 跳过 APIPA
                return iface, a.address
    return None, None


# ============================ 物理 IP ============================

def _is_virtual_iface(iface_name):
    lower = iface_name.lower()
    return any(kw.lower() in lower for kw in VIRTUAL_EXCLUDE)


def get_physical_ips():
    """拿物理网卡的 IPv4（排除虚拟网卡、APIPA 169.254.x.x）"""
    result = []
    for iface, addrs in psutil.net_if_addrs().items():
        if _is_virtual_iface(iface):
            continue
        if not any(kw.lower() in iface.lower() for kw in PHYSICAL_KEYWORDS):
            continue
        for a in addrs:
            if a.family == socket.AF_INET and not a.address.startswith('127.'):
                if a.address.startswith('169.254.'):
                    continue
                result.append({"iface": iface, "ip": a.address})
    return result


# ============================ 邮件正文格式化 ============================

def format_ip_section(title, items):
    if not items:
        return "{}: (none)\n".format(title)
    lines = ["{}:".format(title)]
    for it in items:
        lines.append("  - {} -> {}".format(it["iface"], it["ip"]))
    return "\n".join(lines) + "\n"


# ============================ 主流程 ============================

if __name__ == "__main__":
    # 1) 从 route print 拿所有匹配的 VPN 网卡
    vpn_candidates = get_vpn_macs_from_route(VPN_NAME_KEYWORDS)
    print("VPN candidates from route print:")
    for c in vpn_candidates:
        print("  keyword={}, mac={}, desc={}".format(c['keyword'], c['mac'], c['desc']))

    # 2) 用每个 MAC 反查 VPN 虚拟 IP
    vpn_ips = []
    seen_macs = set()
    for c in vpn_candidates:
        mac = c['mac']
        if mac in seen_macs:
            continue
        seen_macs.add(mac)
        iface, ip = get_ip_by_mac(mac)
        if ip:
            vpn_ips.append({"iface": iface, "ip": ip, "mac": mac, "keyword": c['keyword']})
        else:
            print("MAC {} 在 psutil 里没找到对应 IPv4，VPN 可能未连接。".format(mac))

    # 3) 物理 IP
    physical_ips = get_physical_ips()

    print("Physical IPs:", physical_ips)
    print("VPN IPs     :", vpn_ips)

    # 4) 变化检测 + 发邮件
    result = {
        "physical": physical_ips,
        "vpn": vpn_ips,
    }

    whether_to_send, _ = get_temp_ip(result)
    if whether_to_send:
        content = (
            format_ip_section("\nPhysical IP", physical_ips) +
            format_ip_section("\nVPN IP", vpn_ips)
        )
        send_an_email(content)
    else:
        print("wait and no send")