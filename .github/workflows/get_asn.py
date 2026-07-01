import requests
import ipaddress
import yaml
import time
import random
from collections import defaultdict

OPERATOR_URLS = {
    'mobile': [
        'https://gaoyifan.github.io/china-operator-ip/cmcc.txt',
        'https://gaoyifan.github.io/china-operator-ip/cmcc6.txt'
    ],
    'unicom': [
        'https://gaoyifan.github.io/china-operator-ip/unicom.txt',
        'https://gaoyifan.github.io/china-operator-ip/unicom6.txt'
    ],
    'telecom': [
        'https://gaoyifan.github.io/china-operator-ip/chinanet.txt',
        'https://gaoyifan.github.io/china-operator-ip/chinanet6.txt'
    ]
}

def get_asn_bgpview(ip):
    try:
        response = requests.get(f'https://api.bgpview.io/ip/{ip}', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'ok':
                return data['data']['asn']['asn']
    except:
        pass
    return None

def get_asn_ipapi(ip):
    try:
        response = requests.get(f'http://ip-api.com/json/{ip}?fields=as', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'as' in data:
                return data['as'].split()[0][2:]  # 提取AS号码
    except:
        pass
    return None

def get_asn_ipwhois(ip):
    try:
        response = requests.get(f'http://ipwhois.app/json/{ip}?objects=asn', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'asn' in data:
                return data['asn']
    except:
        pass
    return None

def get_asn_ipinfo(ip):
    try:
        response = requests.get(f'https://ipinfo.io/{ip}/json', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if 'org' in data:
                return data['org'].split()[0][2:]  # 提取AS号码
    except:
        pass
    return None

def get_asn_for_ip(ip):
    # 随机打乱API顺序
    api_functions = [get_asn_bgpview, get_asn_ipapi, get_asn_ipwhois, get_asn_ipinfo]
    random.shuffle(api_functions)
    
    for api_func in api_functions:
        asn = api_func(ip)
        if asn:
            return asn
        time.sleep(random.uniform(1, 2))  # 随机延迟
    return None

def get_cidrs_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        return [line.strip() for line in response.text.split('\n') if line.strip()]
    except:
        return []

def process_operator(name, urls):
    asn_set = set()
    ip_cache = {}
    
    # 准备API函数
    api_functions = [get_asn_bgpview, get_asn_ipapi, get_asn_ipwhois, get_asn_ipinfo]
    
    for url in urls:
        print(f'Processing {url}')
        cidrs = get_cidrs_from_url(url)
        total = len(cidrs)
        
        # 平均分配CIDR到API
        chunk_size = (total + len(api_functions) - 1) // len(api_functions)
        
        for i, cidr in enumerate(cidrs):
            try:
                network = ipaddress.ip_network(cidr)
                first_ip = str(next(network.hosts()))
                
                # 根据索引选择API
                api_index = i // chunk_size
                if api_index >= len(api_functions):
                    api_index = len(api_functions) - 1
                    
                asn = api_functions[api_index](first_ip)
                if asn:
                    asn_set.add(asn)
                print(f'Progress: {i+1}/{total} - API {api_index+1} - Found ASN: {asn}')
                
            except Exception as e:
                print(f'Error processing {cidr}: {str(e)}')
                continue

    yaml_data = {
        'payload': [f'SRC-IP-ASN,{asn}' for asn in sorted(asn_set)]
    }

    output_file = f'{name}_asn.yaml'
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False, indent=2)
    print(f'Saved to {output_file}')

def main():
    for operator, urls in OPERATOR_URLS.items():
        print(f'\nProcessing {operator}...')
        process_operator(operator, urls)
        print(f'Completed {operator}')

if __name__ == '__main__':
    main()