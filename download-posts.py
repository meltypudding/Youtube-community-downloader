import requests, json, argparse

a=argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
a.add_argument('--output','-o',dest='o',metavar='OUT',help="save to OUT.*.txt ('-' for stderr)")
a.add_argument('--debug','-v',dest='v',nargs='?',const=True,help=argparse.SUPPRESS)
a.add_argument('--limit',type=int,default=1000,help="download at most LIMIT posts")
a.add_argument('--skip',type=int,default=0,help="skip first SKIP posts")
a.add_argument('--no-comments',action='store_false',dest='c')
a.add_argument('--no-images',action='store_false',dest='i')
a.add_argument('--no-txt',action='store_false',dest='o',help="don't write *.txt")
a.add_argument('--cookies',action='append',default=[])
a.add_argument('--proxy',action='append',default=[])
a.add_argument('--lang',help=argparse.SUPPRESS)
a.add_argument('--summary','-s',dest='s',action='store_true',help="less display")
a.add_argument('url',help="""https://www.youtube.com/@{channel}/community
https://www.youtube.com/@{channel}/membership\t(must specify --cookies)
https://www.youtube.com/channel/{channel-id}/community?lb={post-id}
https://www.youtube.com/post/{post-id}\netc.""")
a=a.parse_args()

s=requests.Session()
for proxy in a.proxy:
	h=proxy.split('://')
	s.proxies[h[0]]=h[1]
for cookies in a.cookies:
	with open(cookies) as f:
		for line in f.readlines():
			if line.strip() and not line.startswith('#'):
				domain,_,path,_,_,name,value=line.split()
				s.cookies.set(name,value,domain=domain,path=path)

s.headers['User-Agent']='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
if a.lang:s.headers['accept-language']=a.lang
try:r=s.get(a.url)
except KeyboardInterrupt:exit(print('KeyboardInterrupt'))
assert r,r

def extract_between(b:bytes,l:bytes,r:bytes)->dict:
	return json.loads(b.partition(l)[2].partition(r)[0])

def extract_context(b:bytes)->dict:
	return extract_between(b,b'"INNERTUBE_CONTEXT":',b',"INNERTUBE_CONTEXT_')

def extract_initial_data(b:bytes)->dict:
	return extract_between(b,b'ytInitialData = ',b';</script>')

def extract_session_id(b:bytes)->str:
	return(b:=b.partition(b'"USER_SESSION_ID":')[2].partition(b',')[0])and json.loads(b)

def extract_tab_contents(j:dict)->list:
	for tab in j["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]:
		if c:=tab["tabRenderer"].get("content"): # ...[tabs]=[tabRenderer]*n+[expandableTabRenderer]
			return c["sectionListRenderer"]["contents"] # only one tabRenderer contains [contents]

session_id=extract_session_id(r.content)
def secure():
	import hashlib,time
	timestamp=str(round(time.time()))
	def hash(apisid):
		a=[session_id,timestamp,s.cookies[apisid],'https://www.youtube.com']
		return'_'.join([timestamp,hashlib.sha1(' '.join(a).encode()).hexdigest(),'u'])
	s.headers.update({'Authorization':' '.join([
		'SAPISIDHASH',hash("SAPISID"),
		'SAPISID1PHASH',hash("__Secure-1PAPISID"),
		'SAPISID3PHASH',hash("__Secure-3PAPISID")]),
					  'X-Goog-AuthUser': '0',
					  'X-Origin': 'https://www.youtube.com',
					  'X-Youtube-Bootstrap-Logged-In': 'true'})

context=extract_context(r.content)
s.headers.update({'X-YouTube-Client-Name':'1',
				  'X-YouTube-Client-Version':context["client"]["clientVersion"],
				  'Origin':'https://www.youtube.com',
				  'content-type':'application/json',
				  'X-Goog-Visitor-Id':context["client"]["visitorData"]})
def browse(e,browse='browse',/,**kwargs):
	if session_id:secure()
	context["clickTracking"]["clickTrackingParams"]=e["clickTrackingParams"]
	try:r=s.post(f'https://www.youtube.com/youtubei/v1/{browse}?prettyPrint=false',
				 json={'context':context}|kwargs)
	except KeyboardInterrupt:exit(print('KeyboardInterrupt'))
	if session_id and r.status_code==500:exit(print(r,'Cookies expired?'+hint))
	assert r,r
	return json.loads(r.content)

hint='\nHint: Log out from YouTube in the browser you exported cookies from to prevent the cookies being rotated.'
if a.cookies and not session_id:
	print('Warning: Cookies specified but no session detected.'+hint)
def print_hint(msg:str):
	print_hint.once=print_hint.once and print(msg)
print_hint.once=not session_id

def search(contents:list,key:str)->dict:
	if len(contents)==1:
		if c:=contents[0].get(key):
			return c
	if a.v:log(f'searching {key}, get:',contents)
	for i in contents:
		if c:=i.get(key):
			return c

def pop(contents:list,key:str)->dict:
	if len(contents)==2:
		if c:=contents[0].get(key):
			del contents[0]
			return c
	if a.v:log(f'searching leading {key}, get:',contents)
	for l,i in enumerate(contents):
		if c:=i.get(key):
			del contents[l]
			return c

def dig(items:list,*keys:str)->(dict,...):
	for item in items:
		for key in keys:
			item=item[key]
		yield item

def log(message:str,j:list|dict):
	log.write(j)
	print(message)
	if isinstance(j,dict):print(j.keys())
	else:
		for i in j:print(i.keys())

r=extract_initial_data(r.content)
if "contents" not in r:exit(print("Empty page received. Is it a members-only post?"))
contents=extract_tab_contents(r)
if len(contents)>3:
	if a.v:
		for i in contents:
			v=[i]
			if c:=i.get("itemSectionRenderer"):v+=c["contents"]
			print(*map(list,v),sep='\n\t')
	exit(print("No posts here. Check the url"))

if a.s:
	_print=print
	def print(note=None,*args):
		if note is None:return
		if note=='Image':return _print(f'{args[0]:8}',end='\t',flush=True)
		if note=='Post':print.counts=[0,0,0]
		if str(note)[0]=='\t':
			if note.endswith('Page'):return
			type=note.lstrip('\t')
			if not args:args='-',
			elif type=='Image':
				print.counts[0]+=1
				if print.counts[0]>1:
					args=print.counts[0],'images',' '*5
			elif type=='Comment':args+='comments',
			elif type=='Reply':
				print.counts[1]+=1
				print.counts[2]+=args[0]==1
				args=print.counts[1],'replies to',print.counts[2],'comments'
			note='\t'*[0,4,6,0,8][len(note)-len(type)]+'\b'
		else:_print()
		_print(note,*args,end='\r')

def appending(out,ext):
	def no_write(_):pass
	def write(j:dict|list):
		json.dump(j,f,ensure_ascii=False)
		f.write('\n')
	if out=='-':
		import sys
		f=sys.stderr
	elif isinstance(out,str):
		f=open(out+ext,'a',encoding='utf-8')
	else:
		return no_write
	return write

url=a.url.partition('?')
path=url[0].split('/')[-2:]
post_id=path[0]=='post'and path[1]or('&'+url[2]).partition('&lb=')[2].partition('&')[0]
if a.o is None:
	a.o=post_id or'.'.join(path)
dump=appending(a.o,'.raw.txt')
save=appending(a.o,'.minimal.txt')
log.write=appending(a.v,'.txt')

image_dir='images'
if a.i:
	import os
	os.makedirs(image_dir,exist_ok=True)
	image_dir+=os.path.sep
def download_image(url,name=None,dir=image_dir,format='.png'):
	if name:print('Image',name)
	else:name=url.rpartition('/')[2].partition('=')[0]
	if os.path.isfile(p:=dir+name+format):return a.v and print('Image already exists:',p)
	try:r=requests.get(url,proxies=s.proxies)
	except KeyboardInterrupt:exit(print('KeyboardInterrupt'))
	assert r,r
	with open(dir+name+format,'wb') as img:
		img.write(r.content)

def save_perks(content:dict):
	perks=content["expandableItems"]
	output={'num':0,'membership':perks}
	if c:=content.get("bottomButton"):
		e=c["buttonRenderer"]["serviceEndpoint"]
		r=browse(e,'ypc/get_offers',itemParams=e["ypcGetOffersEndpoint"]["params"])
		output['upgrade']=search(r["actions"],"openPopupAction")["popup"]["sponsorshipsOfferRenderer"]
	dump(output)
	summarize(output)
	save(output)
	if not a.i:return
	path=image_dir+a.url.split('/')[-2]+os.path.sep
	for perk in dig(perks,"sponsorshipsPerkRenderer"):
		if c:=perk.get("loyaltyBadges"):
			dir=path+'badges'+os.path.sep
			os.makedirs(dir,exist_ok=True)
			for x in dig(c["sponsorshipsLoyaltyBadgesRenderer"]["loyaltyBadges"],
						 "sponsorshipsLoyaltyBadgeRenderer"):
				name=text(x["title"]).removesuffix(':') # lang-depended, untested
				download_image(x["icon"]["thumbnails"][-1]["url"],name,dir)
		if c:=perk.get("images"):
			dir=path+'emojis'+os.path.sep
			os.makedirs(dir,exist_ok=True)
			for x in c:
				name=x["accessibility"]["accessibilityData"]["label"]
				download_image(x["thumbnails"][-1]["url"],name,dir)

def tier(tier:dict):
	a,b=[],{}
	for perk in dig(tier,"sponsorshipsPerkRenderer"):
		s={"title":text(perk["title"])}
		if c:=perk.get("description"):
			s["description"]=text(c)
		if c:=perk.get("loyaltyBadges"):
			s["images"]=[(
				text(x["title"]).removesuffix(':'),
				x["icon"]["thumbnails"][-1]["url"]
			)for x in dig(
				c["sponsorshipsLoyaltyBadgesRenderer"]["loyaltyBadges"],
				"sponsorshipsLoyaltyBadgeRenderer")]
		if c:=perk.get("images"):
			s["images"]=[(
				x["accessibility"]["accessibilityData"]["label"],
				x["thumbnails"][-1]["url"]
			)for x in c]
		if(t:=s.get("images"))and len(d:=dict(t))==len(t):
			s["images"]=d
		a.append(s)
		b[s["title"]]=s.get("images")or s.get("description")
	return b if len(a)==len(b)else a

def summarize(output:dict):
	output['membership']=tier(output['membership'])
	if c:=output.get('upgrade'):
		output['upgrade']=reduce(c,("tiers",...,"sponsorshipsTierRenderer",{
			"rankId":"rankId",
			"title":(text,"title"),
			"prize":(text,"subtitle"),
			"perks":(tier,"perks","sponsorshipsPerksRenderer","perks")}))

text=lambda d:d.get("simpleText")or''.join(dig(d["runs"],"text"))
number=lambda s:''.join(filter(str.isnumeric,s))

def rich(content:list,inplace:bool=True)->list:
	import urllib
	if not inplace:content=content.copy()
	for i,run in enumerate(content):
		if d:=run.get("navigationEndpoint"):
			if not inplace:run=run.copy()
			if e:=d.get("urlEndpoint"):
				run["url"]=urllib.parse.unquote(e["url"].rpartition('&q=')[2])
				if a.v and run["url"].partition('://')[0]not in('https','http'):
					log('parse error: '+e["url"],d)
			else:
				run["url"]=d["commandMetadata"]["webCommandMetadata"]["url"]
			del run["navigationEndpoint"]
			del run["loggingDirectives"]
			content[i]=run
		if a.v and run.keys()-{"text","bold"}-{"url"}:
			print(run)
	return content

def reduce(i:dict|list,map:dict|tuple|str|int)->dict|list|str:
	if isinstance(map,str):
		return i.get(map)
	elif isinstance(map,int):
		return i[map]
	elif isinstance(map,tuple):
		# map: ([func]? [...|str|int]* [str|int|dict])
		if isinstance(map[0],str|int|dict):
			i=reduce(i,map[0])
			if i and len(map)>1:
				i=reduce(i,map[1:])
		elif map[0] is ...:
			i=[reduce(j,map[1:])for j in i]
		else:
			i=reduce(i,map[1:])
			if i:
				i=map[0](i)
		return i
	else:
		return{k:reduce(i,v)for k,v in map.items()}

def clean(output:dict):
	output['post']=reduce(output['post'],{
		"postId":"postId",
		"author":{
			"label":("authorText","accessibility","accessibilityData","label"),
			"thumbnail":("authorThumbnail","thumbnails",-1,"url"),
			"url":("authorEndpoint","commandMetadata","webCommandMetadata","url")},
		"publishedTime":(text,"publishedTimeText"),
		"content":(rich,"contentText","runs"),
		"likes":(number,"actionButtons","commentActionButtonsRenderer","likeButton","toggleButtonRenderer","accessibility","label"),
		"comments":(number,"actionButtons","commentActionButtonsRenderer","replyButton","buttonRenderer","accessibility","label"),
		"membersonly":(text,"sponsorsOnlyBadge","sponsorsOnlyBadgeRenderer","tooltip"),
		"image":("backstageAttachment","backstageImageRenderer","image","thumbnails",-1,"url"),
		"multiimages":("backstageAttachment","postMultiImageRenderer","images",...,"backstageImageRenderer","image","thumbnails",-1,"url"),
		"video":("backstageAttachment","videoRenderer",{
			"title":(text,"title"),
			"descriptionSnippet":(text,"descriptionSnippet"),
				"publishedTime":(text,"publishedTimeText"),
				"length":(text,"lengthText"),
				"url":("navigationEndpoint","commandMetadata","webCommandMetadata","url"),
				"membersonly":("badges",0,"metadataBadgeRenderer","label"),
				"owner":{
					"text":(text,"ownerText"),
					"badge":("ownerBadges",0,"metadataBadgeRenderer","tooltip"),
					"url":("ownerText","runs",0,"navigationEndpoint","commandMetadata","webCommandMetadata","url")}}),
		"poll":("backstageAttachment","pollRenderer",{
			"totalVotes":(text,"totalVotes"),
			"choices":("choices",...,{
				"text":(text,"text"),
				"image":("image","thumbnails",-1,"url"),
				"ratio":"voteRatioIfNotSelected"})})
	})
	if not(c:=output.get('comments')):return
	if not(len(c['entities'])-1)%5==len(c['replies'])%5==0:
		return print('error: comments in wrong format')
	comments,replies=[],{}
	comment=lambda c,e,d:{k:v for k,v in(reduce(c,("payload","commentEntityPayload",{
		"commentId":("properties","commentId"),
		"avatar":("author","avatarThumbnailUrl"),
		"name":("author","displayName"),
		"badge":("author","sponsorBadgeA11y"),
		"publishedTime":("properties","publishedTime"),
		"content":("properties","content","content"),
		"likeCount":(number,"toolbar","likeButtonA11y"),
	}|({"replyCount":(number,"toolbar","replyCountA11y")}if d else{})
	))|reduce(e,("payload","engagementToolbarStateEntityPayload",{
		"hearted":("TOOLBAR_HEART_STATE_HEARTED".__eq__,"heartState")
	}))).items()if v}
	for entity,entity2 in zip(c['entities'][1::5],c['entities'][5::5]):
		comments.append(comment(entity,entity2,True))
		if'0'!=comments[-1]["replyCount"]:
			replies[comments[-1]["commentId"]]=comments[-1]["replies"]=[]
	for entity,entity2 in zip(c['replies'][::5],c['replies'][4::5]):
		reply=comment(entity,entity2,False)
		ref=replies.get(reply["commentId"].split('.')[0])
		if ref is None:print('error error reply')
		else:ref.append(reply)
	output['comments']=comments

def save_opened_post(post:dict,comments:dict,output:dict):
	post=search(post,"backstagePostThreadRenderer")["post"]["backstagePostRenderer"]
	# the inner post json doesn't include comments count
	output.setdefault('post',post)

	if a.i:
		if c:=post.get("backstageAttachment"):
			images=[]
			if x:=c.get("backstageImageRenderer"):
				images=[x]
			elif x:=c.get("postMultiImageRenderer"):
				images=dig(x["images"],"backstageImageRenderer")
			elif x:=c.get("videoRenderer"):
				print('\tVideo',text(x.get("lengthText")or x["title"]))
			elif x:=c.get("pollRenderer"):
				print('\tPoll',text(x["totalVotes"]))
				print_hint("Hint: Log in to get poll result.")
				images=[i for i in x["choices"]if"image"in i]
			elif a.v:
				log('unrecognized '+"backstageAttachment",c)
			for x in images:
				img=x["image"]["thumbnails"][-1]
				print('\tImage',img["width"],'x',img["height"])
				download_image(img["url"])
		else:print('\tNo Image')

	if a.c:
		entities,replies=[],[]
		for count,comment in enumerate(scroll_down(
				comments,"commentThreadRenderer",'\tComment Page',header="commentsHeaderRenderer",
				continuation_first=True,updates=entities,all_empty_message='\t\tNo comments'),1):
			print('\t\tComment',count)
			if c:=comment.get("replies"):
				for i,_ in enumerate(scroll_down(
						c["commentRepliesRenderer"]["contents"],"commentViewModel",'\t\t\tReply Page',
						continuation_first=True,updates=replies),1):
					print('\t\t\t\tReply',i)
		output['comments']={'entities':entities,'replies':replies}
		print()

def scroll_down(items_growing:list,key:str=None,note:str=None,page_empty_message:str=None,key2:str=None,handle=None,
				continuation_first:bool=False,updates:list=None,header:str=None,all_empty_message:str=None):
	if a.v and continuation_first:
		search(items_growing,"continuationItemRenderer")
	page_count=1
	item_count_this_page=0
	for item in items_growing:
		if c:=item.get(key):
			yield c
			item_count_this_page+=1
		elif c:=item.get("continuationItemRenderer"):
			if not item_count_this_page:
				if continuation_first and page_count==1:
					continuation_first=False
					page_count=0
				elif page_empty_message:
					print(page_empty_message)
				elif a.v:
					print('error: getting empty page')
			if a.v and item is not items_growing[-1]:
				print('error: next page inserting')

			page_count+=1
			item_count_this_page=0
			if note:print(note,page_count)
			e=c.get("continuationEndpoint")or c["button"]["buttonRenderer"]["command"]
			r=browse(e,continuation=e["continuationCommand"]["token"])
			if updates is not None:
				updates+=r["frameworkUpdates"]["entityBatchUpdate"]["mutations"]

			i=r.get("onResponseReceivedEndpoints")or a.v and print('fall to',r.keys())or\
				r.get("onResponseReceivedActions")
			if not i:return print('load next page failed')
			if page_count==1 and header:
				load="reloadContinuationItemsCommand"
				h=pop(i,load)
				j=search(i,load)
				if header_handle:
					header_handle(search(h["continuationItems"],header))
					if not key:return
				if all_empty_message and "continuationItems" not in j:
					return print(all_empty_message)
			else:j=search(i,"appendContinuationItemsAction")
			items_growing+=j["continuationItems"]
		elif key2 and(c:=item.get(key2)):
			handle(c)
			item_count_this_page+=1
		elif a.v:
			log(f'gathering {key}, unknown item:',item)

header_handle=a.v and id

skip=a.skip
def print_video_post(video):
	skip or print('Video',' -- '.join(map(text,(c:=video.get("lengthText"))and
										  [c,video["publishedTimeText"]]or[video["title"]])))

if any(reduce(contents[0],("itemSectionRenderer","contents",...,"sponsorshipsAlertRenderer"))):
	contents.pop(0)

if any("sponsorshipsExpandablePerksRenderer"in i for i in contents):
	save_perks(pop(contents,"sponsorshipsExpandablePerksRenderer"))

if len(contents)==2:
	def header_handle(r):header_handle.comments_count=number(text(r["countText"]))
	print('Post',post_id)
	post,comments=dig(contents,"itemSectionRenderer","contents")
	save_opened_post(post,comments,output:={})
	dump(output)
	clean(output)
	if not a.c:sum(scroll_down(comments,header="commentsHeaderRenderer",continuation_first=True))
	output['post']['comments']=header_handle.comments_count
	save(output)
	exit()

all_posts=search(contents,"itemSectionRenderer")["contents"]

for post_count,post in enumerate(dig(scroll_down(
		all_posts,"backstagePostThreadRenderer",'Post Page',
		'Empty page.',key2="videoRenderer",handle=print_video_post),"post","backstagePostRenderer"),1):
	skip=post_count<a.skip
	if post_count<=a.skip:continue
	if post_count>a.skip+a.limit:break
	print('Post',post_count,' --',text(post["publishedTimeText"]))
	output={'num':post_count,'post':post}

	if a.c or a.i:
		e=post["actionButtons"]["commentActionButtonsRenderer"]["replyButton"]["buttonRenderer"]["navigationEndpoint"]
		r=browse(e,browseId=e["browseEndpoint"]["browseId"],params=e["browseEndpoint"]["params"])
		contents=extract_tab_contents(r)
		post_details=dig(contents,"itemSectionRenderer","contents")
		if len(contents)!=2:log('error: open post! skip',post_details)
		else:save_opened_post(*post_details,output)

	dump(output)
	clean(output)
	save(output)

try:post
except NameError:print("No posts.")
