import requests
from bs4 import BeautifulSoup
import os
import shutil
import ipaddress
import re
import tempfile

# 函数：合并CIDR
def merge_cidrs(cidrs):
    networks = []
    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            networks.append(network)
        except ValueError as e:
            print(f"警告：无法解析CIDR {cidr}：{e}")

    networks.sort()
    merged = []
    for network in networks:
        if not merged:
            merged.append(network)
        else:
            last = merged[-1]
            if last.supernet_of(network):
                continue
            elif last.overlaps(network):
                merged[-1] = ipaddress.ip_network(last.supernet_of(network), strict=False)
            else:
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
            if country_title == 'China':
                asns.append(asn_link.text)
                print(f"找到{isp_name} ASN: {asn_link.text}")

    if not asns:
        print(f"警告：未能为ISP {isp_name}找到任何中国大陆的ASN。")
    else:
        print(f"为 {isp_name} 找到 {len(asns)} 个ASN")

    return list(set(asns))  # 去重

# 从指定的ASN页面获取CIDR（支持缓存）
def get_cidrs(asn, cache_dir, temp_ipv4_file, temp_ipv6_file):
    cache_file_v4 = os.path.join(cache_dir, f"{asn}_prefixes.html")
    cache_file_v6 = os.path.join(cache_dir, f"{asn}_prefixes6.html")

    for cache_file, url_suffix in [(cache_file_v4, "#_prefixes"), (cache_file_v6, "#_prefixes6")]:
        if not os.path.exists(cache_file):
            print(f"正在下载并缓存ASN {asn} 的{url_suffix[1:]}网页...")
            asn_url = f"https://bgp.he.net/{asn}{url_suffix}"
            response = requests.get(asn_url)
            with open(cache_file, "w", encoding="utf-8") as file:
                file.write(response.text)
        else:
            print(f"使用缓存的ASN {asn} 的{url_suffix[1:]}网页...")

        with open(cache_file, "r", encoding="utf-8") as file:
            content = file.read()

        soup = BeautifulSoup(content, "html.parser")
        
        for row in soup.find_all('tr'):
            cidr_link = row.find('a', href=lambda href: href and href.startswith('/net/'))
            if cidr_link:
                cidr_text = cidr_link.text.strip()
                if re.match(r'^\d{1,3}(\.\d{1,3}){3}(\/\d{1,2})?$|^[0-9a-fA-F:]+(\/\d{1,3})?$', cidr_text):
                    if ':' in cidr_text:  # IPv6
                        temp_ipv6_file.write(f"{cidr_text}\n")
                    else:  # IPv4
                        temp_ipv4_file.write(f"{cidr_text}\n")

# 清空缓存目录
def clear_cache(cache_dir):
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

# 主函数
def main(isps, cache_dir):
    clear_cache(cache_dir)

    for isp in isps:
        print(f"正在搜索ISP: {isp}")
        isp_name = isp.split('[')[0].strip()
        ipv4_file_path = f"{isp_name}_v4.txt"
        ipv6_file_path = f"{isp_name}_v6.txt"
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_ipv4_file, \
             tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_ipv6_file:
            
            for search_term in isp.split('[')[1].split(']')[0].split(','):
                search_term = search_term.strip()
                print(f"搜索ISP名称: {search_term}")
                asns = get_asns(search_term)

                for asn in asns:
                    print(f"ASN: {asn}")
                    get_cidrs(asn, cache_dir, temp_ipv4_file, temp_ipv6_file)

            # 处理CIDR并合并
            for temp_file, file_path in zip([temp_ipv4_file, temp_ipv6_file], [ipv4_file_path, ipv6_file_path]):
                temp_file.seek(0)
                cidrs = temp_file.readlines()
                cidrs = merge_cidrs([cidr.strip() for cidr in cidrs])
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    for cidr in cidrs:
                        f.write(f"{cidr}\n")

                print(f"{isp_name} 的CIDR已保存到 {file_path}，数量: {len(cidrs)}")

        # 删除临时文件
        os.unlink(temp_ipv4_file.name)
        os.unlink(temp_ipv6_file.name)

    clear_cache(cache_dir)

# 输入ISP列表和缓存目录
isps_to_search = [
    "China Mobile [mobile, tietong]",
    "China Unicom [cnc, cncgroup, unicom]",
    "China Telecom [chinatelecom, telecom, chinanet, inter+exchange, ct]"
]
cache_dir = "cache"

if __name__ == "__main__":
    main(isps_to_search, cache_dir)
