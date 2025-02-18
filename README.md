Download all community posts (including comments and images) from a YouTube channel.
### Examples
```
download-posts.py https://www.youtube.com/@***/community
download-posts.py https://www.youtube.com/@***/membership --cookies cookies.txt
```
Outputs one post per line in json format to txt files.
### Reminder
- There doesn't seems to be a way to get the exact published time of a post or comment, but only an approximate time (like 1 year ago). Therefore you may like to take a note of the time when you ran the script.
- The output file `*.minimal.txt` stores the most useful data, and further data is stored in `*.raw.txt`. Note that `*.raw.txt` may contain some user data such as **your** account name.
- For how to use cookies and the risks, read this: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies.
---
Here's a handy python code that converts the entire output file into a single json, then you can view it on a json formatter site.
```
python -c "with open(input('input file: '),encoding='utf-8')as i, open(input('output file: '),'w',encoding='utf-8')as o:o.write(','.join(i.readlines()).join('[]'))"
```
If any type of post isn't handled correctly by this script, you're welcome to provide it.
