import requests
from bs4 import BeautifulSoup
import os
import shutil
import ipaddress
import re

# 函数：合并CIDR
def merge_cidrs(cidrs):
    try:
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
    except Exception as e:
        print(f"合并CIDR时发生错误：{e}")
        print(f"问题CIDR列表：{cidrs}")
        return cidrs  # 如果合并失败，返回原始列表

# 从搜索页面提取ASN编号
def get_asns(isp_info):
    isp_name, search_keywords = isp_info.split('[')
    isp_name = isp_name.strip()
    search_keywords = [k.strip().lower() for k in search_keywords[:-1].split(',')]
    
    all_asns = []
    for keyword in [isp_name] + search_keywords:
        search_url = f"https://bgp.he.net/search?search%5Bsearch%5D={keyword}&commit=Search"
        try:
            response = requests.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            for row in soup.find_all('tr'):
                asn_link = row.find('a')
                country_div = row.find('div', class_='flag')
                if asn_link and 'AS' in asn_link.text and country_div:
                    country_title = country_div.get('title', '')
                    td_elements = row.find_all('td')
                    if len(td_elements) >= 3:
                        description = td_elements[2].text.lower()
                        if country_title == 'China' or 'china' in description:
                            if any(kw in description for kw in search_keywords):
                                all_asns.append(asn_link.text)
                                print(f"找到{isp_name} ASN: {asn_link.text}, 描述: {description}")
                            else:
                                print(f"未匹配的ASN: {asn_link.text}, 描述: {description}")
        except Exception as e:
            print(f"搜索关键词 {keyword} 时发生错误: {e}")

    unique_asns = list(set(all_asns))
    print(f"为 {isp_name} 找到 {len(unique_asns)} 个唯一ASN")
    return unique_asns

# 从指定的ASN页面获取CIDR（支持缓存）
def get_cidrs(asn, cache_dir):
    cache_file_v4 = os.path.join(cache_dir, f"{asn}_prefixes.html")
    cache_file_v6 = os.path.join(cache_dir, f"{asn}_prefixes6.html")
    
    cidrs = []
    
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
                cidr_text = cidr_link.text
                if re.match(r'^\d{1,3}(\.\d{1,3}){3}(\/\d{1,2})?$|^[0-9a-fA-F:]+(\/\d{1,3})?$', cidr_text):
                    cidrs.append(cidr_text)

    if not cidrs:
        print(f"警告：未能从ASN {asn}获取任何CIDR。请检查网页结构是否发生变化。")
    else:
        print(f"从ASN {asn}获取了 {len(cidrs)} 个CIDR。")

    return cidrs

# 清空缓存目录
def clear_cache(cache_dir):
    if os.path.exists(cache_dir):
        print(f"清空缓存目录 {cache_dir}...")
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

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
            if len(td_elements) >= 3:
                description = td_elements[2].text.lower()
                if country_title == 'China' or 'china' in description:
                    if isp_name == "China Mobile" and any(name in description for name in ['china mobile']):
                        asns.append(asn_link.text)
                        print(f"找到China Mobile ASN: {asn_link.text}, 描述: {description}")
                    elif isp_name == "China Unicom" and any(name in description for name in ['china unicom', 'cnc', 'cncgroup', 'unicom']):
                        asns.append(asn_link.text)
                        print(f"找到China Unicom ASN: {asn_link.text}, 描述: {description}")
                    elif isp_name == "China Telecom" and any(name.lower() in description for name in ['chinatelecom', 'chinanet', 'china telecom', 'inter exchange', 'telecom', 'ct']):
                        asns.append(asn_link.text)
                        print(f"找到China Telecom ASN: {asn_link.text}, 描述: {description}")
                    else:
                        print(f"未匹配的ASN: {asn_link.text}, 描述: {description}")
    if not asns:
        print(f"警告：未能为ISP {isp_name}找到任何中国大陆的ASN。请检查搜索结果页面结构是否发生变化。")
    else:
        print(f"为 {isp_name} 找到 {len(asns)} 个ASN")

    return asns
# 主函数
def main(isps, cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    for isp_info in isps:
        isp_name = isp_info.split('[')[0].strip()
        print(f"正在搜索ISP: {isp_name}")
        
        ipv4_cache_file = os.path.join(cache_dir, f"{isp_name.replace(' ', '_')}_v4_cache.txt")
        ipv6_cache_file = os.path.join(cache_dir, f"{isp_name.replace(' ', '_')}_v6_cache.txt")
        
        asns = get_asns(isp_info)
        
        with open(ipv4_cache_file, 'w') as ipv4_cache, open(ipv6_cache_file, 'w') as ipv6_cache:
            for asn in asns:
                print(f"ASN: {asn}")
                cidrs = get_cidrs(asn, cache_dir)
                
                for cidr in cidrs:
                    if ':' in cidr:  # IPv6
                        ipv6_cache.write(f"{cidr}\n")
                    else:  # IPv4
                        ipv4_cache.write(f"{cidr}\n")
                
                print(f"从ASN {asn}获取了 {len(cidrs)} 个CIDR。")
        
        # 处理缓存文件并生成最终文件
        for ip_version in ['v4', 'v6']:
            cache_file = os.path.join(cache_dir, f"{isp_name.replace(' ', '_')}_{ip_version}_cache.txt")
            final_file = f"{isp_name.replace(' ', '_')}_{ip_version}.txt"
            
            with open(cache_file, 'r') as f:
                cidrs = [line.strip() for line in f if line.strip()]
            
            print(f"开始合并 {isp_name} {ip_version} CIDR，原始数量: {len(cidrs)}")
            merged_cidrs = merge_cidrs(cidrs)
            
            with open(final_file, 'w') as f:
                for cidr in merged_cidrs:
                    f.write(f"{cidr}\n")
            
            print(f"{isp_name} {ip_version} CIDR合并完成，合并后数量: {len(merged_cidrs)}")
            print(f"文件保存路径：{os.path.abspath(final_file)}")

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
