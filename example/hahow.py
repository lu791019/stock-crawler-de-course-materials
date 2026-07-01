import requests
import math
import time
import pandas as pd

def crawler_hahow_course(category: str):

    category = "programming"
    # 取得總頁數
    url = f'https://api.hahow.in/api/products/search?category=COURSE&groups={category}'
    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    page_limit = response.json()['_metadata']['limit']
    total_count = response.json()['_metadata']['count']

    course_list = []
    # 爬取每一頁的資料
    for p in range(1, math.ceil(total_count / page_limit) + 1):
        url = f'https://api.hahow.in/api/products/search?category=COURSE&groups={category}&page={p}'
        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        print(f"category: {category}, page:{p}, status_code:{response.status_code}")
        if response.status_code == 200:
            courses = response.json()['data']['courseData']['products']
            for course in courses:
                id = course.get('_id')
                uniquename = course.get('uniquename')
                title = course.get('title')
                status = course.get('status')
                link = 'https://hahow.in/courses/' + str(course.get('_id'))
                price = course.get('price')
                preordered_price = course.get('preOrderedPrice')
                average_rating = course.get('averageRating')
                num_rating = course.get('numRating')
                owner_name = course.get('owner', {}).get('name')
                sold_num = course.get('numSoldTickets')
                bookmark_count = course.get('bookmarkCount')
                meta_description = course.get('metaDescription')
                cover_image = course.get('coverImage', {}).get('url')
                incubate_time = course.get('incubateTime')
                publish_time = course.get('publishTime')
                video_length = course.get('totalVideoLengthInSeconds')

                course_dict = {
                    "id": id,
                    "category": category,
                    "uniquename": uniquename,
                    "title": title,
                    "status": status,
                    "link": link,
                    "price": price,
                    "preordered_price": preordered_price,
                    "average_rating": average_rating,
                    "num_rating": num_rating,
                    "owner_name": owner_name,
                    "sold_num": sold_num,
                    "bookmark_count": bookmark_count,
                    "meta_description": meta_description,
                    "cover_image": cover_image,
                    "incubate_time": incubate_time,
                    "publish_time": publish_time,
                    "video_length": video_length,
                }
                print(course_dict)
                course_list.append(course_dict) # 每次新增單筆課程資料

        else:
            print(f"Fetch {url} failed.")

        time.sleep(1)

    df = pd.DataFrame(course_list)
    df.to_csv(f"hahow_course_{category}.csv", index=False, encoding='utf-8-sig')
    print(f"hahow_course_{category}.csv saved.")
    # return df

crawler_hahow_course("programming")
