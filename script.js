document.querySelectorAll(".post").forEach(post => {
	const comments=post.nextElementSibling;
	if(comments){
		comments.hidden=true;
		post.querySelector(".comments").addEventListener("click",()=>{comments.hidden^=true})
	}
});
document.querySelectorAll(".buttons").forEach(buttons => {
	const replies=buttons.nextElementSibling;
	if(replies){
		replies.hidden=true;
		buttons.lastElementChild.addEventListener("click",()=>{replies.hidden^=true})
	}
});
document.querySelectorAll(".content").forEach(content => {
	const clamped=content.scrollHeight > content.clientHeight;
	if(!clamped)return;
	const expander=document.importNode(document.querySelector("template").content,true);
	const [more,less]=expander.children;
	more.addEventListener("click",()=>{
		[content.style.webkitLineClamp,more.style.display,less.style.display]=['none','none',null]
	});
	less.addEventListener("click",()=>{
		[content.style.webkitLineClamp,more.style.display,less.style.display]=[null,null,'none']
	});
	less.style.display='none';
	content.after(expander)
});
document.querySelectorAll(".multiimages").forEach(multiimages => {
	let scrollCount=0,maxScrollCount=multiimages.childElementCount-1,width=multiimages.clientWidth;
	const images=document.createElement("div");
	const arrows=document.importNode(document.querySelector("template").content,true);
	const [left,right]=arrows.children;
	left.addEventListener("click",()=>{
		--scrollCount;
		[left.style.display,right.style.display]=[0 < scrollCount ? null : 'none', null];
		images.style.transform="translateX(-" + scrollCount * width + "px)";
	});
	right.addEventListener("click",()=>{
		++scrollCount;
		[left.style.display,right.style.display]=[null, scrollCount < maxScrollCount ? null : 'none'];
		images.style.transform="translateX(-" + scrollCount * width + "px)";
	});
	left.style.display='none';
	const container=document.createElement("div");
	container.replaceChildren(images);
	images.replaceChildren(...multiimages.children);
	multiimages.replaceChildren(container,left,right)
});
document.querySelectorAll("li").forEach(choice => {
	choice.addEventListener("click",()=>choice.classList.toggle("selected"));
	if(choice.hasAttribute("data-image")){
		const image=document.createElement("img");
		image.setAttribute("src",choice.getAttribute("data-image"));
		choice.prepend(image)
	}
	if(choice.hasAttribute("data-ratio")){
		const text=document.createElement("span");
		const bar=document.createElement("div");
		text.textContent=bar.style.width=Math.round(choice.getAttribute("data-ratio")*100)+'%';
		choice.append(text,bar)
	}
});
document.querySelectorAll(".post img").forEach(image => {
	image.addEventListener("error", ()=>{
		if(!image.hasAttribute("data-src")){
			let url=image.getAttribute("src");
			image.setAttribute("data-src",url);
			image.setAttribute("src",'images/'+url.replace(/.*\/|=.*/g,'')+'.png')
		}
	})
});
const postId=new URLSearchParams(window.location.search).get('lb');
if(postId){
	const post=document.getElementById(postId),parent=post.parentElement;
	const comments=parent.lastElementChild,previous=post.previousElementSibling;
	document.body.replaceChildren(parent);
	if(previous)parent.removeChild(previous);
	if(comments)comments.hidden=false;
}
