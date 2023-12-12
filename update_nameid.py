import requests
import csv
import main as main_file

def get_data(page, token):
    url = f"https://saas.tansiling.com/device/applet/device/list?page={page}&name=&sortType=1"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json;charset=UTF-8',
    }
    response = requests.get(url, headers=headers, proxies=None)
    return response.json()

def write_to_csv(writer, data):
    for item in data:
        item_id = item['id']
        item_name = item['name']
        partition = item['partition']
        instruments = ", ".join([instrument['name'] for instrument in item['instruments']])
        writer.writerow([item_id, item_name, partition, instruments])

def main():
    page = 1
    data_fetched = True
    token = main_file.login()

    with open('devices_data.csv', 'w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['ID', 'Name', 'Partition', 'Instruments'])

        while data_fetched:
            data = get_data(page, token)
            if 'data' in data and len(data['data']) > 0:
                write_to_csv(csv_writer, data['data'])
                page += 1
                print(data)
            else:
                data_fetched = False

if __name__ == "__main__":
    main()