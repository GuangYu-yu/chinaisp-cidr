import requests
from bs4 import BeautifulSoup
import os
import shutil
import ipaddress

# 函数：合并CIDR
def merge_cidrs(cidrs):
    merged = []
    sorted_cidrs = sorted(ipaddress.ip_network(cidr) for cidr in cidrs)

    for cidr in sorted_cidrs:
        if not merged:
            merged.append(cidr)
        else:
            if cidr.supernet_of(merged[-1]):
                merged[-1] = cidr
            elif cidr.overlaps(merged[-1]):
                merged[-1] = merged[-1].supernet()
            else:
                merged.append(cidr)

    return [str(cidr) for cidr in merged]

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
        country_div = row.find('div', class_='flag')
        if asn_link and 'AS' in asn_link.text and country_div and 'China' in country_div['title']:
            asns.append(asn_link.text)

    return asns

# 清空缓存目录
def clear_cache(cache_dir):
    if os.path.exists(cache_dir):
        print(f"清空缓存目录 {cache_dir}...")
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

# 函数：主流程，遍历ISP，获取ASN和CIDR并保存到不同的文件
def main(isps, cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    for isp in isps:
        print(f"正在搜索ISP: {isp}")
        asns = get_asns(isp)
        ipv4_cidrs = []
        ipv6_cidrs = []

        for asn in asns:
            print(f"ASN: {asn}")
            cidrs = get_cidrs(asn, cache_dir)

            for cidr in cidrs:
                if ':' in cidr:
                    ipv6_cidrs.append(cidr)
                else:
                    ipv4_cidrs.append(cidr)

            print(f"{len(cidrs)} 个CIDR已保存。")

        # 合并CIDR并写入文件
        merged_ipv4 = merge_cidrs(ipv4_cidrs)
        merged_ipv6 = merge_cidrs(ipv6_cidrs)

        with open(f"{isp.replace(' ', '_')}_v4.txt", mode='w', encoding='utf-8') as ipv4_file, \
             open(f"{isp.replace(' ', '_')}_v6.txt", mode='w', encoding='utf-8') as ipv6_file:
            for cidr in merged_ipv4:
                ipv4_file.write(f"{cidr}\n")
            for cidr in merged_ipv6:
                ipv6_file.write(f"{cidr}\n")

        print(f"完成 {isp} 的CIDR保存。")
        print("-" * 40)

    # 清空缓存
    clear_cache(cache_dir)

# 输入ISP列表、缓存目录
isps_to_search = ["China Mobile", "China Unicom", "China Telecom"]
cache_dir = "cache"

if __name__ == "__main__":
    main(isps_to_search, cache_dir)
