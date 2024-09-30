import requests
from bs4 import BeautifulSoup
import os
import shutil
import ipaddress

# 函数：合并CIDR
def merge_cidrs(cidrs):
    if not cidrs:  # 如果列表为空
        return []

    # 将CIDR转换为网络对象并排序
    networks = sorted(ipaddress.ip_network(cidr) for cidr in cidrs)
    merged = [networks[0]]

    for current in networks[1:]:
        last = merged[-1]
        if current.subnet_of(last):
            continue
        if last.supernet_of(current):
            merged[-1] = last.supernet()
        elif last.overlaps(current):
            merged[-1] = ipaddress.ip_network(f"{last.network_address}/{last.prefixlen}")
        else:
            merged.append(current)

    return [str(net) for net in merged]

# 函数：从指定的ASN页面获取CIDR（支持缓存）
def get_cidrs(asn, cache_dir):
    cache_file = os.path.join(cache_dir, f"{asn}_prefixes.html")
    
    if not os.path.exists(cache_file):
        print(f"正在下载并缓存ASN {asn} 的prefixes网页...")
        asn_url = f"https://bgp.he.net/{asn}#_prefixes"
        response = requests.get(asn_url)
        with open(cache_file, "w", encoding="utf-8") as file:
            file.write(response.text)
    else:
        print(f"使用缓存的ASN {asn} 的prefixes网页...")

    with open(cache_file, "r", encoding="utf-8") as file:
        content = file.read()

    soup = BeautifulSoup(content, "html.parser")
    cidrs = []
    for row in soup.find_all('tr'):
        cidr = row.find('a')
        if cidr and '/net/' in cidr['href']:
            cidrs.append(cidr.text)

    return cidrs

# 函数：从搜索页面提取ASN编号
def get_asns(isp_name):
    search_url = f"https://bgp.he.net/search?search%5Bsearch%5D={isp_name}&commit=Search"
    response = requests.get(search_url)
    soup = BeautifulSoup(response.content, "html.parser")
    
    asns = []
    for row in soup.find_all('tr'):
        asn_link = row.find('a')
        if asn_link and 'AS' in asn_link.text:
            asns.append(asn_link.text)
    
    return asns

# 清空缓存目录
def clear_cache(cache_dir):
    if os.path.exists(cache_dir):
        print(f"清空缓存目录 {cache_dir}...")
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

# 函数：主流程，遍历ISP，获取ASN和CIDR并保存到六个txt文件
def main(isps, cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    for isp in isps:
        ipv4_cidrs = []
        ipv6_cidrs = []
        
        print(f"正在搜索ISP: {isp}")
        asns = get_asns(isp)
        for asn in asns:
            print(f"ASN: {asn}")
            cidrs = get_cidrs(asn, cache_dir)
            
            # 分别保存到不同的列表
            for cidr in cidrs:
                if ':' in cidr:  # 如果CIDR中有冒号，则是IPv6
                    ipv6_cidrs.append(cidr)
                else:  # 否则为IPv4
                    ipv4_cidrs.append(cidr)

            print(f"{len(cidrs)} 个CIDR已保存。")
        print("-" * 40)

        # 合并CIDR并保存到文件
        merged_ipv4 = merge_cidrs(ipv4_cidrs)
        merged_ipv6 = merge_cidrs(ipv6_cidrs)
        
        # 保存到对应的文件
        with open(f"{isp.replace(' ', '_')}_v4.txt", mode='w', encoding='utf-8') as ipv4_file:
            for cidr in merged_ipv4:
                ipv4_file.write(f"{cidr}\n")
        
        with open(f"{isp.replace(' ', '_')}_v6.txt", mode='w', encoding='utf-8') as ipv6_file:
            for cidr in merged_ipv6:
                ipv6_file.write(f"{cidr}\n")

    # 清空缓存
    clear_cache(cache_dir)

# 输入ISP列表和缓存目录
isps_to_search = ["China Mobile", "China Unicom", "China Telecom"]
cache_dir = "cache"

if __name__ == "__main__":
    main(isps_to_search, cache_dir)
