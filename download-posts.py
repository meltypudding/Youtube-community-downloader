import requests, json, argparse, pathlib

A=argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
A.add_argument('--limit',type=int,default=1000,help="download at most LIMIT posts")
A.add_argument('--skip',type=int,default=0,help="skip first SKIP posts")
A.add_argument('--html',action=argparse.BooleanOptionalAction,default=True)
A.add_argument('--images',action=argparse.BooleanOptionalAction,default=True)
A.add_argument('--comments',action=argparse.BooleanOptionalAction,default=True)
A.add_argument('--cookies')
A.add_argument('--proxy')
A.add_argument('--lang',help="language tags")
A.add_argument('--loglevel',type=int,default=1,help="0 - quiet; 1 - summary; 2 - verbose")
A.add_argument('--debug','-v',action='store_true',help="show error messages")
A.add_argument('--txt','-a',action='store_true',help="same as --err --raw --min")
A.add_argument('--err',action='store_true',help="dump unexpected json to err.txt")
A.add_argument('--raw',action='store_true',help="dump raw json of posts to raw.txt")
A.add_argument('--min',action='store_true',help="dump brief json of posts to min.txt")
A.add_argument('urls',nargs='*',help="""https://www.youtube.com/@{channel}/posts
https://www.youtube.com/@{channel}/membership\t(must specify --cookies)
https://www.youtube.com/channel/{channel-id}/community?lb={post-id}
https://www.youtube.com/post/{post-id}\netc.""")

def start(url):
	global channel,browse,logged_out,s,proxies,tab,post_id
	s=requests.Session()
	proxies=s.proxies
	if a.proxy:
		h=a.proxy.split('://')[-1]
		if h.startswith(':'):a.proxy=a.proxy.replace(h,'127.0.0.1'+h)
		proxies['https']=a.proxy
	if a.cookies:
		with open(a.cookies) as f:
			for line in f.readlines():
				if line.strip() and not line.startswith('#'):
					domain,_,path,_,_,name,value=line.split()
					s.cookies.set(name,value,domain=domain,path=path)

	s.headers['User-Agent']='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
	if a.lang:
		if s.cookies:s.cookies.set('PREF','hl='+a.lang,domain='.youtube.com')
		else:s.headers['accept-language']=a.lang
	elif not s.cookies:
		import locale
		s.headers['accept-language']=locale.getdefaultlocale()[0]
	try:r=s.get(url)
	except KeyboardInterrupt:raise KeyboardInterrupt from None
	r.raise_for_status()

	def extract_between(b:bytes,l:bytes,r:bytes,d=b'')->dict:
		return json.loads(b.partition(l)[2].partition(r)[0]or d)

	def extract_context(b:bytes)->dict:
		return extract_between(b,b'"INNERTUBE_CONTEXT":',b',"INNERTUBE_CONTEXT_')

	def extract_initial_data(b:bytes)->dict:
		return extract_between(b,b'ytInitialData = ',b';</script>')

	def extract_session_id(b:bytes)->str:
		return extract_between(b,b'"USER_SESSION_ID":',b',',b'""')

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
		except KeyboardInterrupt:raise KeyboardInterrupt from None
		if session_id and r.status_code==500:print(r,'Cookies expired?'+logged_out_hint)
		r.raise_for_status()
		return json.loads(r.content)

	logged_out=not session_id
	logged_out_hint='\nHint: Log out from YouTube in the browser you exported cookies from to prevent the cookies being rotated.'
	if a.cookies and logged_out:
		print('Warning: Cookies specified but no session detected.'+logged_out_hint)

	tab,_,query=(path:=url.split('/'))[-1].partition('?')
	post_id=path[-2]=='post'and tab or('&'+query).partition('&lb=')[2].partition('&')[0]

	r=extract_initial_data(r.content)
	channel=(c:=reduce(r,("metadata","channelMetadataRenderer",["vanityChannelUrl","channelUrl"])))and c[0].rpartition('/')[2]
	return r

def set_options(args:list|str=None,**kwargs):
	global a
	if isinstance(args,str):args=args.split()
	a=A.parse_intermixed_args(args)
	update_options(**kwargs)
def update_options(**kwargs):
	vars(a).update(kwargs)
	if a.txt:a.err=a.raw=a.min=True
	a.v=a.debug|a.err

def dump(j:json,out:str):
	if not getattr(a,out):return
	if not hasattr(dump,out):
		setattr(dump,out,open(out+'.txt','a',encoding='utf-8'))
	f=getattr(dump,out)
	json.dump(j,f,ensure_ascii=False)
	f.write('\n')
#dump.err=sys.stderr
#dump(j,'debug')
#dump.debug.flush()

html_name=lambda:f'{channel}.{tab}',lambda:'post.'+post_id
image_name=lambda url:url.rpartition('/')[2].partition('=')[0]
image_dir=pathlib.Path('images')
def download_image(url,name='',dir=image_dir,format='.png'):
	if not name:name=image_name(url)
	dest,temp=dir/(name+format),dir/(name+'.tmp')
	if dest.is_file():return a.debug and print('Image already exists:',dest)
	try:r=requests.get(url,proxies=proxies)
	except KeyboardInterrupt:raise KeyboardInterrupt from None
	r.raise_for_status()
	dir.mkdir(parents=True,exist_ok=True)
	temp.write_bytes(r.content)
	temp.rename(dest)

def save_perks(content:dict):
	output={'num':0,'membership':reduce(content,(
		"perkCards",0,"sponsorshipsHubPerkCardViewModel","onTap","innertubeCommand",
		"showEngagementPanelEndpoint","engagementPanel","engagementPanelSectionListRenderer",
		"content","sectionListRenderer","contents")),'content':content}
	output['perks']=search(output['membership'],"sponsorshipsPerksListViewModel")["perks"]
	if e:=reduce(content,("manageButton","buttonViewModel","onTap","innertubeCommand")):
		r=browse(e,'ypc/get_offers',itemParams=e["ypcGetOffersEndpoint"]["params"])
		output['upgrade']=search(r["actions"],"openPopupAction")["popup"]["sponsorshipsOfferRenderer"]
	dump(output,'raw')
	summarize(output)
	dump(output,'min')
	if a.html:make_html(output,*perks_html)
	if not a.images:return
	path=image_dir/channel
	for perk in output['perks']:
		if c:=perk.get("emoji"):
			print_tabs('Images',perk["title"])
			for x in c:
				download_image(x["sources"][0]["url"],'',path/'emojis')
			print_endline()
		if c:=perk.get("badges"):
			for x in c:
				print_tabs('Image',name:=x["title"])
				download_image(x["image"]["sources"][0]["url"],name,path/'badges')
			print_endline()
	for perk in reduce(output,('upgrade',0,"perks",dict.values))or[]:
		if isinstance(perk,list):
			for label,url in perk:
				print_tabs('Image',label)
				download_image(url,'',path/'badges')
			print_endline()
		if isinstance(perk,dict):
			for name,url in perk.items():
				print_tabs('Image',name)
				download_image(url,name,path/'emojis')
			print_endline()

def summarize(output:dict):
	del output['membership'],output['content']
	if c:=output.get('upgrade'):
		output['upgrade']=reduce(c,("tiers",...,"sponsorshipsTierRenderer",{
			"rankId":"rankId",
			"title":(text,"title"),
			"prize":(text,"subtitle"),
			"perks":(tier,"perks","sponsorshipsPerksRenderer","perks",...,"sponsorshipsPerkRenderer")}))

def tier(perks:list):
	a,b=[],{}
	for perk in perks:
		s={"title":text(perk["title"])}
		if c:=perk.get("description"):
			s["description"]=text(c)
		if c:=perk.get("images"):
			t=[(
				x["accessibility"]["accessibilityData"]["label"],
				x["thumbnails"][-1]["url"]
			)for x in c]
			s["images"]=max(dict(t),t,key=len)
		a.append(s)
		b[s["title"]]=s.get("images")or s.get("description")
	return max(b,a,key=len)

attachmentRuns="attachmentRuns",...,{
	"start":"startIndex","length":"length",
	"url":("element","type","imageType","image","sources",-1,"url"),
	"label":("element","properties","accessibilityProperties","label")}
attachmentRuns_check=False
def js_len(s):
	l=[]
	for i,c in enumerate(s):
		if ord(c)>65535:l.append(i)
		l.append(i)
	l.append(len(s))
	return l
def get_comments_emojis(output,once={}):
	if not(c:=output['comments']):return
	m=isinstance(c,list)
	channel=reduce(output['post'],('author','url')if m else("authorEndpoint","commandMetadata","webCommandMetadata","url")).removeprefix('/')
	once=once.setdefault(channel,set())
	path=image_dir/channel/'emojis'
	for i in c if m else reduce(c['entities'][1::5]+c['replies'][::5],(...,"payload","commentEntityPayload","properties","content")):
		if attachmentRuns_check:index=js_len(i["content"])
		for a in reduce(i,"emojis"if m else attachmentRuns)or[]:
			if attachmentRuns_check:
				l=i["content"][index[a["start"]]:index[a["start"]+a["length"]]]
				if(':_',':')!=(l[:2],l[-1]):continue
				if l[2:-1]!=a["label"]:log(l,i)
			if'/emoji_u'in a["url"]:continue
			if(name:=a["label"])not in once:
				once.add(name)
				download_image(a["url"],name,path)

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
		if'\r\n'in run["text"]:run["text"]=run["text"].replace('\r\n','\n')
	return content

def reduce(i:dict|list,map:dict|list|tuple|str|int)->dict|list|str:
	if isinstance(map,str):
		return i.get(map)
	elif isinstance(map,int):
		return i[map]if~len(i)<map<len(i)else None
	elif isinstance(map,tuple):
		# map: ([func|...|str|int]* [list|dict]?)
		if not map:pass
		elif callable(map[0]):
			if(i:=reduce(i,map[1:])):
				i=map[0](i)
		elif map[0] is ...:
			i=[reduce(j,map[1:])for j in i]
		else:
			if(i:=reduce(i,map[0])):
				i=reduce(i,map[1:])
		return i
	elif isinstance(map,list):
		return[r for v in map if(r:=reduce(i,v))]
	else:
		return{k:r for k,v in map.items()if(r:=reduce(i,v))or type(r)in(int,str)}

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
			"thumbnail":("thumbnail","thumbnails",-1,"url"),
			"title":(text,"title"),
			"descriptionSnippet":(text,"descriptionSnippet"),
			"publishedTime":(text,"publishedTimeText"),
			"length":(text,"lengthText"),
			"views":(text,"viewCountText"),
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
	if r:=output.get('re-post'):output['re-post']=reduce(r,{
			"postId":"postId",
			"author":{
				"label":("displayName","accessibility","accessibilityData","label"),
				"thumbnail":("thumbnail","thumbnails",-1,"url"),
				"url":("endpoint","commandMetadata","webCommandMetadata","url")},
			"publishedTime":(text,"publishedTimeText"),
			"content":(rich,"content","runs")
	})
	if'commentCount'in output:output['post']["comments"]=number(output.pop('commentCount'))
	if not(c:=output.get('comments')):return
	if not(len(c['entities'])-1)%5==len(c['replies'])%5==0:
		return print('error: comments in wrong format')
	comments,replies=[],{}
	comment=lambda c,e:reduce(c,("payload","commentEntityPayload",{
		"commentId":("properties","commentId"),
		"avatar":("author","avatarThumbnailUrl"),
		"name":("author","displayName"),
		"badge":("author","sponsorBadgeA11y"),
		"verified":("author","isVerified"),
		"isAuthor":("author","isCreator"),
		"isArtist":("author","isArtist"),
		"publishedTime":("properties","publishedTime"),
		"content":("properties","content","content"),
		"emojis":("properties","content",*attachmentRuns),
		"likeCount":(number,"toolbar","likeButtonA11y"),
		"replyCount":(number,"toolbar","replyCountA11y")
	}))|reduce(e,("payload","engagementToolbarStateEntityPayload",{
		"hearted":("TOOLBAR_HEART_STATE_HEARTED".__eq__,"heartState")}))
	for entity,entity2 in zip(c['entities'][1::5],c['entities'][5::5]):
		comments.append(comment(entity,entity2))
		if'0'!=comments[-1]["replyCount"]:
			replies[comments[-1]["commentId"]]=comments[-1]["replies"]=[]
	for entity,entity2 in zip(c['replies'][::5],c['replies'][4::5]):
		reply=comment(entity,entity2)
		ref=replies.get(reply["commentId"].split('.')[0])
		try:
			ref.append(reply)
			del reply["replyCount"]
		except:
			log('error error reply',reply)
	if t:=c.get('pinned'):
		for i in comments:
			if p:=t.get(i["commentId"]):
				i["pinned"]=p
	output['comments']=comments

def log(message:str,j:list[dict]|dict):
	dump(j,'err')
	if a.debug:
		print(message)
		if isinstance(j,dict):print(j.keys())
		else:
			for i in j:print(i.keys())

def log_contents(contents):
	log('contents:',contents)
	for i in reduce(contents,(...,"itemSectionRenderer","contents")):
		if i:log('items:',i)

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

def iprint(indent,type,*values,omit='',debug=None):
	if a.loglevel==2 or debug:
		print('\t'*indent+type,*values)
	elif a.loglevel==1 and debug is None:
		if omit or not values:values=omit or type,
		elif type=='Post':values=type,*values
		elif type=='Image':
			iprint.counts[0]+=1
			if iprint.counts[0]>1:
				values=iprint.counts[0],'images',' '*5
		elif type=='Comment':values+='comments',
		elif type=='Reply':
			iprint.counts[1]+=1
			iprint.counts[2]+=values[0]==1
			values=iprint.counts[1],'replies to',iprint.counts[2],'comments'
		print(end='\r'+'\t'*[0,4,6,0,8][indent])
		print(*values,end='',flush=True)

def print_item(*values):
	if a.loglevel:print(*values)

def print_tabs(type:str,value):
	if a.loglevel==2:print(type,value)
	elif a.loglevel==1:print(end=f'{value:8}\t',flush=True)

def print_endline():
	if a.loglevel==1:print()

def print_once(msg:str,printed=set()):
	msg in printed or printed.add(msg)or print(msg)

def fill_post_details(contents:list,output:dict):
	post_details=reduce(contents,(...,"itemSectionRenderer","contents"))
	if comments_off_message:=reduce(post_details,(0,1,"messageRenderer","text","runs",0,"text")):
		comments={'message':comments_off_message}
		post_details[0].pop()
	elif len(contents)!=2:
		log_contents(contents)
		return print('error: open post! skip')
	else:
		comments={'start':post_details[1]}

	c=search(post_details[0],"backstagePostThreadRenderer")["post"]
	if r:=c.get("sharedPostRenderer"):
		output.setdefault('re-post',r)
		c=r["originalPost"]
	post=c["backstagePostRenderer"]
	comments_cache[post["postId"]]=comments
	if'post'not in output:
		output['post']=post
		# the inner post json doesn't include comments count
		get_comments(output,only_count=True)
	elif c:=post.get("backstageAttachment"):
		output['post']["backstageAttachment"]=c

def get_images(output):
	iprint.counts=[0,0,0]
	if c:=output['post'].get("backstageAttachment"):
		images=[]
		if x:=c.get("backstageImageRenderer"):
			images=[x]
		elif x:=c.get("postMultiImageRenderer"):
			images=dig(x["images"],"backstageImageRenderer")
		elif x:=c.get("videoRenderer"):
			iprint(1,'Video',text(x.get("lengthText")or x["title"]))
		elif x:=c.get("pollRenderer"):
			iprint(1,'Poll',text(x["totalVotes"]))
			logged_out and print_once("\nHint: Log in to get poll result.")
			images=[i for i in x["choices"]if"image"in i]
		elif a.v:
			log('unrecognized '+"backstageAttachment",c)
		for x in images:
			img=x["image"]["thumbnails"][-1]
			iprint(1,'Image',img["width"],'x',img["height"])
			download_image(img["url"])
	else:iprint(1,'No Image',omit='-')

comments_cache={}
def get_comments(output,force_reload=False,only_count=False):
	iprint.counts=[0,0,0]
	if'start'not in(c:=comments_cache[output['post']["postId"]]):
		output['message']=c['message']
		iprint(2,c['message'])
		return
	if force_reload:
		c=comments_cache[output['post']["postId"]]={'start':c['start'][:1]}
	if'iter'not in c:
		c['load']={'entities':[],'replies':[]}
		c['iter']=enumerate(scroll_down(
			c['start'],"commentThreadRenderer",header="commentsHeaderRenderer",
			type='Comment',indent=1,first_empty_page=True,updates=c['load']['entities'],all_empty_message='No comments'))
	if only_count and'count'in c:
		output['commentCount']=c['count']
		return
	for count,comment in c['iter']:
		if count==0:
			c['count']=text(comment["countText"])
			if only_count:
				output['commentCount']=c['count']
				return
			continue
		if p:=(q:=(r:=comment["commentThreadRenderer"])["commentViewModel"]["commentViewModel"]).get("pinnedText"):
			c['load'].setdefault('pinned',{})[q["commentId"]]=p
		iprint(2,'Comment',count)
		if r:=r.get("replies"):
			for i,_ in enumerate(scroll_down(
					r["commentRepliesRenderer"]["contents"],"commentViewModel",
					type='Reply',indent=3,first_empty_page=True,updates=c['load']['replies']),1):
				iprint(4,'Reply',i)
	output['comments']=c['load']
	if a.images:get_comments_emojis(output)

def scroll_down(items_growing:list,*keys:str,header:str=None,type:str=None,indent:int=0,page_empty_ok:bool=False,
				first_empty_page:bool|int=False,updates:list=None,all_empty_message:str=None):
	if a.v and first_empty_page:
		search(items_growing,"continuationItemRenderer")
	page_count=1-first_empty_page
	item_count_this_page=0
	for item in items_growing:
		if any(key in item for key in keys):
			yield item
			item_count_this_page+=1
		elif c:=item.get("continuationItemRenderer"):
			if not item_count_this_page and page_count>0:
				if page_empty_ok:iprint(indent+1,'Empty page.',debug=a.v)
				elif a.v:print('error: getting empty page')
			if a.v and item is not items_growing[-1]:
				print('error: next page inserting')

			page_count+=1
			item_count_this_page=0
			if type:iprint(indent,type,'Page',page_count,debug=a.v>indent)
			e=c.get("continuationEndpoint")or c["button"]["buttonRenderer"]["command"]
			r=browse(e,continuation=e["continuationCommand"]["token"])
			if updates is not None:
				try:updates+=r["frameworkUpdates"]["entityBatchUpdate"]["mutations"]
				except:a.v and log('error: update empty',r)

			if not(i:=r.get("onResponseReceivedEndpoints")):
				if a.debug:print('fall to',r.keys())
				if not(i:=r.get("onResponseReceivedActions")):
					return log('load next page failed',r)
			if page_count==1 and header:
				load="reloadContinuationItemsCommand"
				yield search(pop(i,load)["continuationItems"],header)
				if not(j:=search(i,load).get("continuationItems")):
					if all_empty_message:iprint(indent+1,all_empty_message,omit='-')
					elif a.v:print('error: all empty')
					continue
			elif not(j:=search(i,"appendContinuationItemsAction").get("continuationItems")):
				if a.v:print('error: append empty')
				continue
			items_growing+=j
		elif a.v:
			log(f'gathering {"/".join(keys)}, unknown item:',item)

def is_single_post(contents):
	return len(contents)==2 or reduce(contents,(0,"itemSectionRenderer","contents",any,...,"messageRenderer"))

def is_snippet(output):
	return"replyButton"in output['post']["actionButtons"]["commentActionButtonsRenderer"]

def open_post(output):
	e=reduce(output,['re-post','post'])[0]["publishedTimeText"]["runs"][0]["navigationEndpoint"]
	r=browse(e,browseId=e["browseEndpoint"]["browseId"],params=e["browseEndpoint"]["params"])
	fill_post_details(extract_tab_contents(r),output)

def extract_tab_contents(j:dict)->list:
	for tab in j["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]:
		if c:=tab["tabRenderer"].get("content"): # ...[tabs]=[tabRenderer]*n+[expandableTabRenderer]
			return c["sectionListRenderer"]["contents"] # only one tabRenderer contains [contents]

def get_posts(url):
	r=start(url)
	if"contents"not in r:
		if a.v:log('page:',r)
		return print("Empty page received. Is it a members-only post?")
	contents=extract_tab_contents(r)
	if is_single_post(contents):
		start_html(html_name[1]())
		fill_post_details(contents,output:={})
		yield output
	elif len(contents)==1 or(perks:=reduce(contents,(0,"sponsorshipsHubViewModel"))):
		start_html(html_name[0]())
		if contents[:-1] and perks:save_perks(perks)
		yield from get_posts_from_contents(contents[-1:])
	else:
		if a.v:log_contents(contents)
		return print("No posts here. Check the url")
	finish_html()

def get_posts_from_contents(contents):
	all_posts=search(contents,"itemSectionRenderer")["contents"]
	for post in scroll_down(all_posts,"backstagePostThreadRenderer","videoRenderer",type='Post',page_empty_ok=True):
		output=reduce(post,{
			'post':("backstagePostThreadRenderer","post","backstagePostRenderer"),
			're-post':("backstagePostThreadRenderer","post","sharedPostRenderer"),
			'video-post':"videoRenderer"})
		if r:=output.get('re-post'):output['post']=r["originalPost"]["backstagePostRenderer"]
		yield output
	try:post
	except NameError:print("No posts.")

def get_posts_from_urls(*urls):
	for url in urls:
		print_item('\n'+url)
		yield from get_posts(url)

def run(urls,limit=1000,skip=0,post_count=0):
	for output in get_posts_from_urls(*urls):
		if c:=output.get('video-post'):
			if post_count>=skip:
				print_item('Video',' -- '.join(map(text,reduce(c,["lengthText","publishedTimeText","title"]))))
			continue
		post_count+=1
		if post_count<=skip:continue
		if post_count>skip+limit:break
		save_post(post_count,output)

def save_post(post_count,output):
	iprint(0,'Post',post_count,' --',text(reduce(output,['re-post','post'])[0]["publishedTimeText"]))
	output={'num':post_count}|output
	if a.images|a.comments:
		if is_snippet(output):open_post(output)
		if a.images:get_images(output)
		if a.comments:get_comments(output)
		print_item()
	else:
		print_endline()
	save(output)
def save(output):
	dump(output,'raw')
	clean(output)
	dump(output,'min')
	write_html(output)
def write_html(output):
	if not a.html:return
	global channel
	if not globals().get('channel'):channel=reduce(output,('post','author','url')).removeprefix('/')
	make_html(output,*post_html)

def start_html(name):
	if not a.html:return
	if not(f:=pathlib.Path('style.css')).is_file():
		f.write_text(css)
	if not(f:=pathlib.Path('script.js')).is_file():
		f.write_text(js)
	g=(f:=pathlib.Path(name+'.html')).is_file()
	global html
	html=f.open('a',encoding='utf-8')
	if g:return
	html.write('<link href="style.css" rel="stylesheet"/>')
	html.write('<script src="script.js" defer></script>')
	html.write(f'<template>{more_button+less_button}</template>')

def make_html(data:dict|list|str, tag:str|tuple, *operations):
	if isinstance(data, list):
		for entry in data:
			make_html(entry, tag, *operations)
		return
	while isinstance(tag, tuple):
		if args := tag[0] in data and tag[1:] or operations:
			tag, *operations = args
		else: return
	element=tag
	for item in operations:
		if item == '/':
			html.write(f'<{element}/>')
			return
		elif isinstance(item, str):
			element+=f' class="{item}"'
			data=reduce(data, item)
			if not data: return
		elif isinstance(item, tuple):
			element+=f' class="{"-".join(i for i in item if isinstance(i, str))}"'
			data=reduce(data, item)
			if data is None: return
		elif isinstance(item, set):
			element+=f' class="{" ".join(item)}"'
		elif isinstance(item, dict):
			for attr,value in reduce(data, item).items():
				element+=f' {attr}="{value}"'
		elif isinstance(item, list):
			html.write(f'<{element}>')
			for args in item:
				if isinstance(args, list):
					batch=args[:1]
					for arg in args[1:]:
						batch.append(arg)
						if isinstance(arg, str|tuple|list):
							make_html(data, *batch)
							del batch[1:]
				elif isinstance(args, tuple):
					make_html(data, *args)
			break
	else:html.write(f'<{element}>{data}')
	html.write(f'</{tag}>')

svg='<svg height="24" viewBox="0 0 24 24" width="24"><path d="{}"></path></svg>'.format
hearted=svg("M16.5 3C19.02 3 21 5.19 21 7.99c0 3.7-3.28 6.94-8.25 11.86l-.75.74-.74-.73-.04-.04C6.27 14.92 3 11.69 3 7.99 3 5.19 4.98 3 7.5 3c1.4 0 2.79.71 3.71 1.89L12 5.9l.79-1.01C13.71 3.71 15.1 3 16.5 3Zm0-1c-1.74 0-3.41.88-4.5 2.28C10.91 2.88 9.24 2 7.5 2 4.42 2 2 4.64 2 7.99c0 4.12 3.4 7.48 8.55 12.58L12 22l1.45-1.44C18.6 15.47 22 12.11 22 7.99 22 4.64 19.58 2 16.5 2Z").__mul__
hearted_filled=svg("M16.5 2c-1.74 0-3.41.88-4.5 2.28C10.91 2.88 9.24 2 7.5 2 4.42 2 2 4.64 2 7.99c0 4.12 3.4 7.48 8.55 12.58L12 22l1.45-1.44C18.6 15.47 22 12.11 22 7.99 22 4.64 19.58 2 16.5 2Z").__mul__
verified=svg("M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zM9.8 17.3l-4.2-4.1L7 11.8l2.8 2.7L17 7.4l1.4 1.4-8.6 8.5z").__mul__
like_button=svg("M18.77 11h-4.23l1.52-4.94C16.38 5.03 15.54 4 14.38 4c-.58 0-1.14.24-1.52.65L7 11H3v10h14.43c1.06 0 1.98-.67 2.19-1.61l1.34-6c.27-1.24-.78-2.39-2.19-2.39zM7 20H4v-8h3v8zm12.98-6.83-1.34 6c-.1.48-.61.83-1.21.83H8v-8.61l5.6-6.06c.19-.21.48-.33.78-.33.26 0 .5.11.63.3.07.1.15.26.09.47l-1.52 4.94-.4 1.29h5.58c.41 0 .8.17 1.03.46.13.15.26.4.19.71z")
reply_button=svg("M8 7h8v2H8V7zm0 6h5v-2H8v2zM5 3v13h10.41l.29.29 3.3 3.3V3H5M4 2h16v20l-5-5H4V2z")
more_button=svg("m18 9.28-6.35 6.35-6.37-6.35.72-.71 5.64 5.65 5.65-5.65z")
less_button=svg("M18.4 14.6 12 8.3l-6.4 6.3.8.8L12 9.7l5.6 5.7z")
count=lambda count: count.lstrip('0')
url=lambda url: url.startswith('/') and 'https://www.youtube.com'+url or url

import re
comment=lambda s:re.sub(':_([^:]*):',rf'<img src="{image_dir/channel}/emojis/\1.png" alt=":_\1:">',re.sub(' (@[^ ]*) ',rf'<a href="{url("/")}\1"> \1 </a>',s))

comment_html = [
	('div', {"header"}, [('p', "pinned"), ['span', {'class': (' '.join, {'author': "isAuthor", 'artist': "isArtist", 'verified': "verified"})}, [
		('a', { 'href': (url, '/'.__add__, "name")}, "name")], "badge", "publishedTime"]]),
	('span', (comment, "content")),
	('div', {"buttons"}, [['span', (count, "likeCount"), (hearted, "hearted"), (count, "replyCount")]])
]
post_html = 'div', [('div', "re-post", {'id': "postId"}, [
	('div', {"header"}, [['a', {'href': (url, "author", "url")}, ("author", "label"), {'href': ('?lb='.__add__, "postId")}, "publishedTime"], ('span', "membersonly")]),
	('div', "content", [(("url", 'a', {'href': (url, "url")}, "text"), 'span', "text")]),
]), ('div', "post", {'id': "postId"}, [
	('div', {"header"}, [['a', {'href': (url, "author", "url")}, ("author", "label"), {'href': ('?lb='.__add__, "postId")}, "publishedTime"], ('span', "membersonly")]),
	('div', "content", [(("url", 'a', {'href': (url, "url")}, "text"), 'span', "text")]),
	(("image", 'img', {'src': "image"}, '/'),
	 ("multiimages", 'div', "multiimages", [('img', {'src': ()}, '/')]),
	 ("video", 'div', "video", [('a', {'href': (url, "url")}, [('img', {'src': "thumbnail"}, '/'), ('span', "length")]), ('div', [
		 ('a', {'href': (url, "url")}, "title"),
		 ['span', [('a', "owner", {'href': (url, "url")}, "text"), ['span', "views", "publishedTime"]], "descriptionSnippet", "membersonly"]])]),
	 ("poll", 'div', "poll", [('span', "totalVotes"), ('ul', "choices", [('li', {'data-image': "image", 'data-ratio': "ratio"}, "text")])])),
	('div', {"buttons"}, [['span', (count, "likes"), (count, "comments")]])
]), ('div', {'data-id': ("post", "postId")}, "comments", [('div', {'id': "commentId"}, [
	*comment_html,
	('div', {'data-id': "commentId"}, "replies", [('div', {'id': "commentId"}, comment_html)])
])])]
perks_html = 'div', "perks", [('div', {"perk"}, [
	['p', "title", ("description", "content")],
	('p', "emoji", [('img', {'src': ("sources", 0, "url")}, '/')]),
	('div', "badges", [('div', [('img', {'src': ("image", "sources", 0, "url")}, '/'), ('div', "title")])])
])]

def finish_html():
	if f:=globals().get('html'):f.close()

import atexit
@atexit.register
def finish():
	for f in vars(dump).values():f.close()
	finish_html()

css=r'''.header > * {margin-right: 8px;}span.membersonly, .badge {color: #107516;background-color: rgba(0,0,0,0.05);padding: 0 4px;width: fit-content;}.re-post {margin-bottom: -16px;}.post, .re-post {/* padding: 16px 16px 8px; */padding: 16px 56px 8px 72px;margin-top: 24px;}.post {border: 1px solid rgba(0,0,0,0.1);border-radius: 12px;img {width: 100%;height: fit-content;}}.content {display: -webkit-box;overflow: hidden;-webkit-box-orient: vertical;-webkit-line-clamp: 4;white-space: pre-wrap;/* font-family: Roboto, Arial, sans-serif; */}.video {margin-top: 4px;display: flex;flex-direction: row;> a {position: relative;height: fit-content;margin-right: 8px;img {width: 210px;border-radius: 8px;}span {position: absolute;right: 0;bottom: 0;color: #fff;background: rgba(0,0,0,0.6);border-radius: 4px;padding: 1px 4px;margin: 4px;}}> div {display: flex;flex-direction: column;* span::before {content: "\2022";margin: 6px;font-family: Roboto, Arial, sans-serif;}> span ~ * {margin-top: 8px;}}}div > svg {position: absolute;border-radius: 50%;padding: 8px;cursor: pointer;}.content ~ svg {margin: -32px -40px;fill: #065fd4;&:hover {background: #def1ff;}}.multiimages {display: flex;position: relative;align-items: center;> div {overflow: hidden;}* div {transition-duration: .15s;transition-timing-function: cubic-bezier(.05,0,0,1);display: flex;}img {min-width: 100%;}svg {rotate: 90deg;background-color: #fff;box-shadow: 0 4px 4px rgba(0,0,0,0.1), 0 0 8px rgba(0,0,0,0.1);color: #030303;&:first-of-type {left: -40px;}&:last-of-type {right: -40px;}}}.buttons span {display: inline-flex;padding: 8px;margin: -8px;}:is(.likes, .likeCount)::before {content: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24"><path d="M18.77 11h-4.23l1.52-4.94C16.38 5.03 15.54 4 14.38 4c-.58 0-1.14.24-1.52.65L7 11H3v10h14.43c1.06 0 1.98-.67 2.19-1.61l1.34-6c.27-1.24-.78-2.39-2.19-2.39zM7 20H4v-8h3v8zm12.98-6.83-1.34 6c-.1.48-.61.83-1.21.83H8v-8.61l5.6-6.06c.19-.21.48-.33.78-.33.26 0 .5.11.63.3.07.1.15.26.09.47l-1.52 4.94-.4 1.29h5.58c.41 0 .8.17 1.03.46.13.15.26.4.19.71z"></path></svg>');}span.comments, .replyCount {&::before {content: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24"><path d="M8 7h8v2H8V7zm0 6h5v-2H8v2zM5 3v13h10.41l.29.29 3.3 3.3V3H5M4 2h16v20l-5-5H4V2z"></path></svg>');}border-radius: 20px;&:not(:empty) {cursor: pointer;}&:hover {background: rgba(0,0,0,0.1);}}div.comments {padding: 0 40px 0 56px;> div {margin-bottom: 16px;}.content a {color: #065fd4;}}.replies {padding-left: 40px;> div {margin-bottom: 8px;}}.pinned {margin: 0 0 8px;}.author {background-color: #888888;&, .name {color: #ffffff;}border-radius: 12px;padding: 1px 6px;}.verified::after {display: inline-block;content: '';mask: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24"><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zM9.8 17.3l-4.2-4.1L7 11.8l2.8 2.7L17 7.4l1.4 1.4-8.6 8.5z"></path></svg>');mask-size: cover;background-color: currentColor;width: 12px;height: 12px;margin-left: 4px;vertical-align: middle;}.artist::after {display: inline-block;content: '';mask: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" height="12" viewBox="0 0 12 12" width="12"><path clip-rule="evenodd" d="M10.334 4.205a1.8 1.8 0 010 3.59 1.8 1.8 0 01-2.539 2.54 1.8 1.8 0 01-3.59-.001 1.8 1.8 0 01-2.538-2.539 1.8 1.8 0 010-3.59 1.8 1.8 0 012.538-2.539 1.8 1.8 0 013.59 0 1.8 1.8 0 012.539 2.539ZM6 3v2.668A1.75 1.75 0 107 7.25V4h1V3H6Z" fill-rule="evenodd"></path></svg>');/* mask: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24"><path clip-rule="evenodd" d="M19.222 9.008a3 3 0 010 5.984 3 3 0 01-4.23 4.232 3 3 0 01-5.984 0 3 3 0 01-4.23-4.232 3 3 0 010-5.984 3 3 0 014.23-4.231 3 3 0 015.984 0 3 3 0 014.23 4.231ZM12 7v5.5a2.5 2.5 0 101 2V10h3V7h-4Z" fill-rule="evenodd"></path></svg>'); */mask-size: cover;background-color: currentColor;width: 12px;height: 12px;margin-left: 4px;vertical-align: middle;}.hearted svg {fill: #f03;width: 20px;}span, .primary, .header a, .title.title {color: #0f0f0f;}.header .publishedTime, .secondary, .video *, p, .totalVotes {color: #606060;}li::before {position: absolute;content: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"></path></svg>');width: 16px;left: -36px;align-self: anchor-center;padding: 10px;}li span {position: absolute;right: 8px;color: inherit;}li div {position: absolute;height: 100%;left: 0;top: 0;border-radius: 4px;z-index: -1;}li.selected {&::before {content: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" fill="%23065fd4" viewBox="0 0 24 24"><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zM9.8 17.3l-4.2-4.1L7 11.8l2.8 2.7L17 7.4l1.4 1.4-8.6 8.5z"></path></svg>');}color: #065fd4;border-color: #065fd4;div {background-color: #def1ff;}}ul:has(.selected) li:not(.selected) {border-color: rgba(0,0,0,0.1);div {background-color: rgba(0,0,0,0.1);}}li {display: flex;align-items: center;position: relative;list-style-type: none;border-radius: 4px;border: 1px solid #030303;padding: 8px;margin: 0 0 12px 0;}ul.choices img {height: 125px;width: fit-content;margin: -8px;margin-right: 16px;}.badges {display: grid;grid-auto-flow: column;div {width: fit-content;justify-items: center;}}p {margin: 0;}a {text-decoration: none;}.header, .video, .totalVotes {font-size: 75%;}.header a:first-of-type {font-size: calc(13% / .12);}.title:not(div) {font-size: initial;}.perk {font-size: 87.5%;border-bottom: 1px solid rgba(0,0,0,0.1);padding-bottom: 12px;padding-top: 16px;}body {align-items: center;display: flex;flex-direction: column;> * {width: 852px;max-width: 100%;}}'''
js=r'''document.querySelectorAll(".post").forEach(post => {const comments=post.nextElementSibling;if(comments){comments.hidden=true;post.querySelector(".comments").addEventListener("click",()=>{comments.hidden^=true})}});document.querySelectorAll(".buttons").forEach(buttons => {const replies=buttons.nextElementSibling;if(replies){replies.hidden=true;buttons.lastElementChild.addEventListener("click",()=>{replies.hidden^=true})}});document.querySelectorAll(".content").forEach(content => {const clamped=content.scrollHeight > content.clientHeight;if(!clamped)return;const expander=document.importNode(document.querySelector("template").content,true);const [more,less]=expander.children;more.addEventListener("click",()=>{[content.style.webkitLineClamp,more.style.display,less.style.display]=['none','none',null]});less.addEventListener("click",()=>{[content.style.webkitLineClamp,more.style.display,less.style.display]=[null,null,'none']});less.style.display='none';content.after(expander)});document.querySelectorAll(".multiimages").forEach(multiimages => {let scrollCount=0,maxScrollCount=multiimages.childElementCount-1,width=multiimages.clientWidth;const images=document.createElement("div");const arrows=document.importNode(document.querySelector("template").content,true);const [left,right]=arrows.children;left.addEventListener("click",()=>{--scrollCount;[left.style.display,right.style.display]=[0 < scrollCount ? null : 'none', null];images.style.transform="translateX(-" + scrollCount * width + "px)";});right.addEventListener("click",()=>{++scrollCount;[left.style.display,right.style.display]=[null, scrollCount < maxScrollCount ? null : 'none'];images.style.transform="translateX(-" + scrollCount * width + "px)";});left.style.display='none';const container=document.createElement("div");container.replaceChildren(images);images.replaceChildren(...multiimages.children);multiimages.replaceChildren(container,left,right)});document.querySelectorAll("li").forEach(choice => {choice.addEventListener("click",()=>choice.classList.toggle("selected"));if(choice.hasAttribute("data-image")){const image=document.createElement("img");image.setAttribute("src",choice.getAttribute("data-image"));choice.prepend(image)}if(choice.hasAttribute("data-ratio")){const text=document.createElement("span");const bar=document.createElement("div");text.textContent=bar.style.width=Math.round(choice.getAttribute("data-ratio")*100)+'%';choice.append(text,bar)}});document.querySelectorAll(".post img").forEach(image => {image.addEventListener("error", ()=>{if(!image.hasAttribute("data-src")){let url=image.getAttribute("src");image.setAttribute("data-src",url);image.setAttribute("src",'images/'+url.replace(/.*\/|=.*/g,'')+'.png')}})});const postId=new URLSearchParams(window.location.search).get('lb');if(postId){const post=document.getElementById(postId),parent=post.parentElement;const comments=parent.lastElementChild,previous=post.previousElementSibling;document.body.replaceChildren(parent);if(previous)parent.removeChild(previous);if(comments)comments.hidden=false;}'''

__all__ =[
	"get_posts_from_urls", "get_posts", "is_snippet", "open_post", "get_images", "get_comments", "get_comments_emojis",
	"set_options", "update_options", "run",
	"start", "extract_tab_contents", "get_posts_from_contents", "start_html", "is_single_post",
	"clean", "save_post", "dump", "save", "write_html", "download_image", "finish", "finish_html"]

if'__main__'!=__name__:
	set_options([])
else:
	set_options()
	if a.urls:run(a.urls,a.limit,a.skip)
	else:A.print_help()
