import requests
from bs4 import BeautifulSoup
import os
import shutil
import ipaddress
import re

# 函数：合并CIDR
def merge_cidrs(cidrs):
    networks = sorted(ipaddress.ip_network(cidr) for cidr in cidrs)
    merged = []
    for network in networks:
        if not merged or not merged[-1].supernet_of(network):
            merged.append(network)
        else:
            while merged and merged[-1].supernet_of(network):
                network = merged.pop().supernet_of(network)
            merged.append(network)
    return [str(net) for net in merged]

# 从搜索页面提取ASN编号
def get_asns(isp_name):
    search_url = f"https://bgp.he.net/search?search%5Bsearch%5D={isp_name}&commit=Search"
    response = requests.get(search_url)
    soup = BeautifulSoup(response.content, "html.parser")

    asns = []
    for row in soup.find_all('tr'):
        asn_link = row.find('a')
        country_div = row.find('div', class_='flag')
        if asn_link and 'AS' in asn_link.text and country_div:
            country_title = country_div.get('title', '')
            td_elements = row.find_all('td')
            if len(td_elements) >= 3 and country_title == 'China' and 'China' in td_elements[2].text:
                asns.append(asn_link.text)

    if not asns:
        print(f"警告：未能为ISP {isp_name}找到任何中国大陆的ASN。请检查搜索结果页面结构是否发生变化。")

    return asns

# 从指定的ASN页面获取CIDR（支持缓存）
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
        cidr_link = row.find('a', href=lambda href: href and href.startswith('/net/'))
        if cidr_link:
            cidr_text = cidr_link.text
            if re.match(r'^\d{1,3}(\.\d{1,3}){3}(\/\d{1,2})?$|^[0-9a-fA-F:]+(\/\d{1,3})?$', cidr_text):
                cidrs.append(cidr_text)

    if not cidrs:
        print(f"警告：未能从ASN {asn}获取任何CIDR。请检查网页结构是否发生变化。")

    return cidrs

# 清空缓存目录
def clear_cache(cache_dir):
    if os.path.exists(cache_dir):
        print(f"清空缓存目录 {cache_dir}...")
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

# 主函数
def main(isps, cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    for isp in isps:
        print(f"正在搜索ISP: {isp}")
        ipv4_file_path = f"{isp.replace(' ', '_')}_v4.txt"
        ipv6_file_path = f"{isp.replace(' ', '_')}_v6.txt"
        
        ipv4_cidrs = []
        ipv6_cidrs = []
        
        asns = get_asns(isp)
        for asn in asns:
            print(f"ASN: {asn}")
            cidrs = get_cidrs(asn, cache_dir)
            
            for cidr in cidrs:
                if ':' in cidr:  # IPv6
                    ipv6_cidrs.append(cidr)
                else:  # IPv4
                    ipv4_cidrs.append(cidr)
            
            print(f"{len(cidrs)} 个中国大陆CIDR已获取。")
        
        # 保存到文件
        with open(ipv4_file_path, mode='w', encoding='utf-8') as ipv4_file:
            for cidr in ipv4_cidrs:
                ipv4_file.write(f"{cidr}\n")
        
        with open(ipv6_file_path, mode='w', encoding='utf-8') as ipv6_file:
            for cidr in ipv6_cidrs:
                ipv6_file.write(f"{cidr}\n")
        
        print(f"{isp} 的中国大陆CIDR已保存。")
        print(f"IPv4 CIDR数量: {len(ipv4_cidrs)}")
        print(f"IPv6 CIDR数量: {len(ipv6_cidrs)}")
        print(f"文件保存路径：\nIPv4: {os.path.abspath(ipv4_file_path)}\nIPv6: {os.path.abspath(ipv6_file_path)}")

    clear_cache(cache_dir)

    # 对六个文件分别进行CIDR合并
    for isp in isps:
        for ip_version in ['v4', 'v6']:
            file_path = f"{isp.replace(' ', '_')}_{ip_version}.txt"
            with open(file_path, 'r') as f:
                cidrs = [line.strip() for line in f if line.strip()]
            
            merged_cidrs = merge_cidrs(cidrs)
            
            with open(file_path, 'w') as f:
                for cidr in merged_cidrs:
                    f.write(f"{cidr}\n")
            
            print(f"{isp} {ip_version} CIDR合并完成，合并后数量: {len(merged_cidrs)}")

# 输入ISP列表和缓存目录
isps_to_search = ["China Mobile", "China Unicom", "China Telecom"]
cache_dir = "cache"

if __name__ == "__main__":
    main(isps_to_search, cache_dir)
