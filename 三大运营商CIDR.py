import requests
from bs4 import BeautifulSoup
import os
import shutil
import ipaddress
import re
import tempfile

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
                    asns.append(asn_link.text)
                    print(f"找到{isp_name} ASN: {asn_link.text}, 描述: {description}")

    if not asns:
        print(f"警告：未能为ISP {isp_name}找到任何中国大陆的ASN。请检查搜索结果页面结构是否发生变化。")
    else:
        print(f"为 {isp_name} 找到 {len(asns)} 个ASN")

    return asns

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
        
        cidr_count = 0
        for row in soup.find_all('tr'):
            cidr_link = row.find('a', href=lambda href: href and href.startswith('/net/'))
            if cidr_link:
                cidr_text = cidr_link.text
                if re.match(r'^\d{1,3}(\.\d{1,3}){3}(\/\d{1,2})?$|^[0-9a-fA-F:]+(\/\d{1,3})?$', cidr_text):
                    if ':' in cidr_text:  # IPv6
                        temp_ipv6_file.write(f"{cidr_text}\n")
                    else:  # IPv4
                        temp_ipv4_file.write(f"{cidr_text}\n")
                    cidr_count += 1

    if cidr_count == 0:
        print(f"警告：未能从ASN {asn}获取任何CIDR。请检查网页结构是否发生变化。")
    else:
        print(f"从ASN {asn}获取了 {cidr_count} 个CIDR。")

# 清空缓存目录
def clear_cache(cache_dir):
    if os.path.exists(cache_dir):
        print(f"清空缓存目录 {cache_dir}...")
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir)

# 排序和合并CIDR函数
def sort_and_merge_cidrs(cidrs):
    ipv4_networks = []
    ipv6_networks = []
    
    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if isinstance(network, ipaddress.IPv4Network):
                ipv4_networks.append(network)
            elif isinstance(network, ipaddress.IPv6Network):
                ipv6_networks.append(network)
        except ValueError as e:
            print(f"警告：无法解析CIDR {cidr}：{e}")
    
    def merge_networks(networks):
        if not networks:
            return []
        sorted_networks = sorted(networks)
        merged = [sorted_networks[0]]
        for net in sorted_networks[1:]:
            last = merged[-1]
            if last.supernet_of(net):
                continue
            elif last.overlaps(net) or last.broadcast_address + 1 == net.network_address:
                merged[-1] = ipaddress.ip_network(last.supernet_of(net), strict=False)
            else:
                merged.append(net)
        return merged
    
    merged_ipv4 = merge_networks(ipv4_networks)
    merged_ipv6 = merge_networks(ipv6_networks)
    
    return [str(net) for net in merged_ipv4], [str(net) for net in merged_ipv6]

# 主函数
def main(isps, cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    for isp in isps:
        print(f"正在搜索ISP: {isp}")
        isp_name = isp.split('[')[0].strip()
        ipv4_file_path = f"{isp_name}_v4.txt"
        ipv6_file_path = f"{isp_name}_v6.txt"
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_ipv4_file, \
             tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_ipv6_file:
            
            # 对每个ISP名称进行搜索
            for search_term in isp.split('[')[1].split(']')[0].split(','):
                search_term = search_term.strip()
                print(f"搜索ISP名称: {search_term}")
                asns = get_asns(search_term)
                
                # 去除重复的ASN
                asns = list(set(asns))
                print(f"总共找到 {len(asns)} 个唯一ASN")

                for asn in asns:
                    print(f"ASN: {asn}")
                    get_cidrs(asn, cache_dir, temp_ipv4_file, temp_ipv6_file)

            # 处理IPv4 CIDR
            temp_ipv4_file.seek(0)
            ipv4_cidrs = temp_ipv4_file.readlines()
            print(f"开始排序和合并 {isp_name} IPv4 CIDR，原始数量: {len(ipv4_cidrs)}")
            ipv4_cidrs = sort_and_merge_cidrs([cidr.strip() for cidr in ipv4_cidrs])
            print(f"{isp_name} IPv4 CIDR排序和合并完成，合并后数量: {len(ipv4_cidrs)}")

            # 处理IPv6 CIDR
            temp_ipv6_file.seek(0)
            ipv6_cidrs = temp_ipv6_file.readlines()
            print(f"开始排序和合并 {isp_name} IPv6 CIDR，原始数量: {len(ipv6_cidrs)}")
            ipv6_cidrs = sort_and_merge_cidrs([cidr.strip() for cidr in ipv6_cidrs])
            print(f"{isp_name} IPv6 CIDR排序和合并完成，合并后数量: {len(ipv6_cidrs)}")

        # 保存到文件
        with open(ipv4_file_path, mode='w', encoding='utf-8') as ipv4_file:
            for cidr in ipv4_cidrs:
                ipv4_file.write(f"{cidr}\n")
        
        with open(ipv6_file_path, mode='w', encoding='utf-8') as ipv6_file:
            for cidr in ipv6_cidrs:
                ipv6_file.write(f"{cidr}\n")
        
        print(f"{isp_name} 的中国大陆CIDR已保存。")
        print(f"IPv4 CIDR数量: {len(ipv4_cidrs)}")
        print(f"IPv6 CIDR数量: {len(ipv6_cidrs)}")
        print(f"文件保存路径：\nIPv4: {os.path.abspath(ipv4_file_path)}\nIPv6: {os.path.abspath(ipv6_file_path)}")

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
