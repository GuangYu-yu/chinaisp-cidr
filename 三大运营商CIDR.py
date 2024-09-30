import requests
from bs4 import BeautifulSoup
import os
import shutil
import ipaddress
import time
import random
import re

# 函数：合并CIDR
def merge_cidrs(cidrs):
    networks = sorted(ipaddress.ip_network(cidr) for cidr in cidrs)
    merged = []
    for network in networks:
        if not merged or network.supernet_of(merged[-1]):
            merged.append(network)
        else:
            while merged and not network.supernet_of(merged[-1]):
                merged.pop()
            merged.append(network)
    return [str(net) for net in merged]

# 更新：添加请求头和延迟
def get_with_retry(url, max_retries=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    for _ in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            time.sleep(random.uniform(1, 3))  # 随机延迟1-3秒
            return response
        except requests.RequestException as e:
            print(f"请求失败: {e}. 正在重试...")
    raise Exception(f"无法获取 {url} 的数据，请检查网络连接。")

# 更新：从搜索页面提取ASN编号
def get_asns(isp_name):
    search_url = f"https://bgp.he.net/search?search%5Bsearch%5D={isp_name}&commit=Search"
    response = get_with_retry(search_url)
    soup = BeautifulSoup(response.content, "html.parser")

    asns = []
    for row in soup.find_all('tr'):
        asn_link = row.find('a')
        country_div = row.find('div', class_='flag')
        if asn_link and 'AS' in asn_link.text and country_div:
            country_title = country_div.get('title', '')
            if country_title == 'China':  # 只包含中国大陆的ASN
                asns.append(asn_link.text)

    if not asns:
        print(f"警告：未能为ISP {isp_name}找到任何中国大陆的ASN。请检查搜索结果页面结构是否发生变化。")

    return asns

# 更新：从指定的ASN页面获取CIDR（支持缓存）
def get_cidrs(asn, cache_dir):
    cache_file = os.path.join(cache_dir, f"{asn}_prefixes.html")
    
    if not os.path.exists(cache_file):
        print(f"正在下载并缓存ASN {asn} 的prefixes网页...")
        asn_url = f"https://bgp.he.net/{asn}#_prefixes"
        response = get_with_retry(asn_url)
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
        country_div = row.find('div', class_='flag')
        if cidr_link and country_div and country_div.get('title') == 'China':
            cidr_text = cidr_link.text
            if re.match(r'^\d{1,3}(\.\d{1,3}){3}(\/\d{1,2})?$|^[0-9a-fA-F:]+(\/\d{1,3})?$', cidr_text):
                cidrs.append(cidr_text)

    if not cidrs:
        print(f"警告：未能从ASN {asn}获取任何中国大陆的CIDR。请检查网页结构是否发生变化。")

    return cidrs

# 清空缓存目录
def clear_cache(cache_dir):
    if os.path.exists(cache_dir):
        print(f"清空缓存目录 {cache_dir}...")
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

# 更新：主流程，添加错误处理和日志
def main(isps, cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    for isp in isps:
        print(f"正在搜索ISP: {isp}")
        try:
            asns = get_asns(isp)
            
            ipv4_cidrs = []
            ipv6_cidrs = []
            
            for asn in asns:
                print(f"ASN: {asn}")
                cidrs = get_cidrs(asn, cache_dir)
                for cidr in cidrs:
                    if ':' in cidr:  # IPv6
                        ipv6_cidrs.append(cidr)
                    else:  # IPv4
                        ipv4_cidrs.append(cidr)
                        
                print(f"{len(cidrs)} 个中国大陆CIDR已获取。")
            
            # 合并CIDR
            merged_ipv4 = merge_cidrs(ipv4_cidrs)
            merged_ipv6 = merge_cidrs(ipv6_cidrs)

            # 保存到文件
            ipv4_file_path = f"{isp.replace(' ', '_')}_v4.txt"
            ipv6_file_path = f"{isp.replace(' ', '_')}_v6.txt"
            
            with open(ipv4_file_path, mode='w', encoding='utf-8') as ipv4_file, \
                 open(ipv6_file_path, mode='w', encoding='utf-8') as ipv6_file:
                for cidr in merged_ipv4:
                    ipv4_file.write(f"{cidr}\n")
                for cidr in merged_ipv6:
                    ipv6_file.write(f"{cidr}\n")

            print(f"{isp} 的中国大陆CIDR已保存。IPv4: {len(merged_ipv4)}个, IPv6: {len(merged_ipv6)}个")
            print(f"文件保存路径：\nIPv4: {os.path.abspath(ipv4_file_path)}\nIPv6: {os.path.abspath(ipv6_file_path)}")
        except Exception as e:
            print(f"处理 {isp} 时发生错误: {e}")

    clear_cache(cache_dir)

# 输入ISP列表和缓存目录
isps_to_search = ["China Mobile", "China Unicom", "China Telecom"]
cache_dir = "cache"

if __name__ == "__main__":
    main(isps_to_search, cache_dir)
