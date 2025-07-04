+ Installation: download [the code](https://raw.githubusercontent.com/meltypudding/Youtube-community-downloader/refs/heads/main/download_posts.py).
+ Requires: Python>=3.10, Requests.
```
> python3 download_post.py https://www.youtube.com/@***/posts
```
```
from download_posts import *
for post in get_posts_from_urls('https://www.youtube.com/@***/posts'):
	clean(post)
	print('-'*60)
	print(post['post']['author']['label'],'\t'+post['post']['publishedTime']+':\n')
	print(''.join(i['text'] for i in post['post']['content']))
```
