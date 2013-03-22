#!/usr/bin/env python

#                                                                                                                                                                                   
# Copyright (c) 2012 CodePill Sp. z o.o.
# Author: Krzysztof Ksiezyk <kksiezyk@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

# ----------------------------------------
# define functions
def clprint(color,txt,nonl=False):
	colours={
		'default':'',
		'yellow': '\x1b[01;33m',
		'blue': '\x1b[01;34m',
		'cyan': '\x1b[01;36m',
		'green': '\x1b[01;32m',
		'red': '\x1b[01;31m'
	}
	if nonl:
		print colours[color]+txt+'\x1b[00m',
	else:
		print colours[color]+txt+'\x1b[00m'
# -----------------------
def gh_request_raw(url,postdata='',only200=False,method='GET'):
	
	if not re.search("^https\:\/\/",url):
		url='https://api.github.com/'+url

	if postdata!='':
		req = urllib2.Request(url,postdata)
	else:
		req = urllib2.Request(url)

	req.add_header('Accept', 'application/json')
	req.add_header('Content-type', 'application/x-www-form-urlencoded')
	req.add_header('Authorization', 'Basic ' + (gh_user + ':' + gh_pass).encode('base64').rstrip())

	if method=='DELETE' or method=='PUT':
		req.get_method= lambda: method

	if method=='PUT':
		req.add_header('Content-Length', '0')

	if debug:
		clprint('cyan','DEBUG: '+method+' request to '+url)

	code=200
	try:
		res = urllib2.urlopen(req)
	except urllib2.HTTPError, error:
		code=error.code
		data=error.read()
		if code not in [401,404,406,422] or (not code==200 and only200):
			clprint ('red','Request error ['+str(error.code)+'] ('+url+')')
			myexit(255)
	else:
		data=res.read()

	data=[code,data]
	return data
# -----------------------
def gh_request_arr(url,postdata='',only200=False,method='GET'):
	res=gh_request_raw(url,postdata,only200,method)
	res[1]=json.JSONDecoder().decode(res[1])
	return res
# -----------------------
def myexit(code=0):
	if os.path.isdir(tmp_dir) and tmp_dir!='/':
		os.system('rm -rf '+tmp_dir)
	sys.exit(code)
# ----------------------------------------
def signal_handler(signal,frame):
	print
	clprint ('yellow','Ctrl-C pressed')
	myexit(254)
# ----------------------------------------

# init
import ConfigParser, signal, sys, os, re, urllib2, json, warnings, time, getpass, pickle

signal.signal(signal.SIGINT, signal_handler)
warnings.filterwarnings("ignore", category=RuntimeWarning)

currdir=os.getcwd()

debug=False
gh_user=''
gh_pass=''
gh_org=''
gh_repo=''
gh_data={}

# parse config
config = ConfigParser.RawConfigParser()
config.read(__file__[:-3]+'.cfg')

def_gh_user=config.get('settings','def_gh_user')
def_gh_org=config.get('settings','def_gh_org')
archive_type=config.get('settings','archive_type')

hostname=config.get('settings','hostname')

tmp_dir=config.get('settings','tmp_dir')
if not os.path.isdir(tmp_dir):
	clprint('red','Temp directory ('+tmp_dir+') doesn\'t exist. Edit '+__file__+'.cfg file.')
	myexit(255)
tmp_dir+='/'+os.path.basename(os.tmpnam()).replace('file','dir')

backup_dir=config.get('settings','backup_dir')
if not os.path.isdir(backup_dir):
	clprint('red','Backup directory ('+tmp_dir+') doesn\'t exist. Edit '+__file__+'.cfg file.')
	myexit(255)

os.makedirs(tmp_dir);
os.makedirs(tmp_dir+"/_textdump");
os.makedirs(tmp_dir+"/_downloads");

# load ssh pub key
try:
	ssh_key=open(config.get('settings','ssh_pub_key_file'),'r').read()
except:
	clprint('red','Cannot load ssh key ('+config.get('settings','ssh_pub_key_file')+'). Edit '+__file__+'.cfg file.')
	myexit(255)

# welcome
print
clprint ('green','Backup github repository')

# gather user input
while gh_user=='':
	gh_user=raw_input('Enter github user name or press \'enter\' for default ['+def_gh_user+']: ')

	if gh_user=='':
		gh_user=def_gh_user
	if not re.search('^[a-z0-9\_\-\.]+$',gh_user,re.I) :
		clprint ('red','\tWrong user name. Allowed chars are letters, digits and \'-_.\'')
		gh_user=''

while gh_pass=='':
	gh_pass=getpass.getpass('Enter github user password: ')

	if gh_pass=='':
		clprint ('red','\tPassword can\'t be empty')

while gh_org=='':
	gh_org=raw_input('Enter github organization (\'-\' for none) or press \'enter\' for default ['+def_gh_org+']: ')

	if gh_org=='':
		gh_org=def_gh_org
	if not re.search('^[a-z0-9\_\-\.]+$',gh_user,re.I) :
		clprint ('red','\tWrong organization name. Allowed chars are letters, digits and \'-_.\'')
		gh_org=''

while gh_repo=='':
	gh_repo=raw_input('Enter github repository name: ')

	if gh_repo=='' or not re.search('^[a-z0-9\_\-\.]+$',gh_repo,re.I) :
		clprint ('red','\tWrong repository name. Allowed chars are letters, digits and \'-_.\'')
		gh_repo=''

# main
gh_data['backup']={}
gh_data['backup']['version']=1
gh_data['backup']['date']=time.strftime("%Y-%m-%d %H:%M:%S")
gh_data['backup']['user']=gh_user
gh_data['backup']['organization']=gh_org
gh_data['backup']['repository']=gh_repo

# check credenials
clprint('blue','Getting user data');
res=gh_request_arr('users/user')
if res[0]==401:
	clprint ('red','Wrong user name or password')
	myexit(255)
else:
	gh_data['user']=res[1]

# check privileges
if gh_org!='-':
	clprint('blue','Checking membership in owners team');
	res=gh_request_arr('orgs/'+gh_org+'/teams')
	if res[0]==404:
		clprint ('red','User is not member of organization '+gh_org+' "owners" team')
		myexit(255)
	else:
		teams=res[1]

	is_member=False
	for team in teams:
		if team['name']=='Owners':
			is_member=True
	
	if is_member==False:
		clprint ('red','User is not member of organization '+gh_org+' "owners" team')
		myexit(255)
	
	del teams
	del is_member

# get repo data
clprint('blue','Getting repository data');
if gh_org!='-':
	gh_repo_url='repos/'+gh_org+'/'+gh_repo
else:
	gh_repo_url='repos/'+gh_user+'/'+gh_repo
	
res=gh_request_arr(gh_repo_url)
if res[0]==404:
	clprint ('red','Repository doesn\'t exist')
	myexit(255)
else:
	gh_data['repo']=res[1]	

# add ssh key
data={'title':hostname,'key':ssh_key}
data=json.JSONEncoder().encode(data)

clprint('blue','Adding deploy ssh key');
res=gh_request_arr(gh_repo_url+'/keys',data)
if res[0]==422:
	clprint ('yellow','\tKey already used');
	gh_data['new_key']=0
else:
	gh_data['new_key']=res[1]

## clone repositories
clprint('blue','Cloning main repository from github');
cmd='cd '+tmp_dir+' && git clone --mirror '+gh_data['repo']['ssh_url']+' ./'+gh_repo+' >/dev/null'
if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
res=os.system(cmd);
if not res==0:
	clprint ('red','Command returned error code '+str(res))
	myexit(255)	
	
if gh_data['repo']['has_wiki']==1:
	clprint('blue','Cloning wiki repository from github');
	cmd='cd '+tmp_dir+' && git clone --mirror '+re.sub('\.git$','.wiki.git',gh_data['repo']['ssh_url'])+' ./'+gh_repo+'.wiki'+' >/dev/null'
	if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
	res=os.system(cmd);
	if not res==0:
		clprint ('red','Command returned error code '+str(res))
		myexit(255)

# remove ssh key
if gh_data['new_key']:
	clprint('blue','Removing deploy ssh key');
	res=gh_request_raw(gh_repo_url+'/keys/'+str(gh_data['new_key']['id']),data,method='DELETE')
del gh_data['new_key']

# keys
clprint('blue','Getting repository keys');
res=gh_request_arr(gh_repo_url+'/keys',only200=True)
gh_data['keys']=res[1]

# collaborators
clprint('blue','Getting repository collaborators');
res=gh_request_arr(gh_repo_url+'/collaborators',only200=True)
gh_data['collaborators']=res[1]

# teams
clprint('blue','Getting repository teams');
res=gh_request_arr(gh_repo_url+'/teams',only200=True)
gh_data['teams']=res[1]

# forks
clprint('blue','Getting repository forks');
res=gh_request_arr(gh_repo_url+'/forks',only200=True)
gh_data['forks']=res[1]

# hooks
clprint('blue','Getting repository hooks');
res=gh_request_arr(gh_repo_url+'/hooks',only200=True)
gh_data['hooks']=res[1]

# labels
clprint('blue','Getting repository labels');
res=gh_request_arr(gh_repo_url+'/labels',only200=True)
gh_data['labels']=res[1]

# milestones
gh_data['milestones']={}
clprint('blue','Getting repository miletstones');
res=gh_request_arr(gh_repo_url+'/milestones?state=open',only200=True)
gh_data['milestones']=res[1]
res=gh_request_arr(gh_repo_url+'/milestones?state=closed',only200=True)
gh_data['milestones'].extend(res[1])

# issues
gh_data['issues']={}

clprint('blue','Getting repository issues');
res=gh_request_arr(gh_repo_url+'/issues?state=open',only200=True)
gh_data['issues']=res[1]
res=gh_request_arr(gh_repo_url+'/issues?state=closed',only200=True)
gh_data['issues'].extend(res[1])

# comments & events
if len(gh_data['issues'])>0:
	gh_data['comments']={}
	gh_data['events']={}
	cnt=0
	print
	for issue in gh_data['issues']:
		cnt+=1
		clprint('blue','\x1B[1AGetting issues comments & events: '+str(cnt)+' / '+str(len(gh_data['issues'])));
		res=gh_request_arr(gh_repo_url+'/issues/'+str(issue['number'])+'/comments',only200=True)
		gh_data['comments'][issue['number']]=res[1]
		res=gh_request_arr(gh_repo_url+'/issues/'+str(issue['number'])+'/events',only200=True)
		gh_data['events'][issue['number']]=res[1]

# downloads
clprint('blue','Getting repository downloads');
res=gh_request_arr(gh_repo_url+'/downloads',only200=True)
gh_data['downloads']=res[1]

if len(gh_data['downloads'])>0:
	clprint('blue','Downloading files');
	for download in gh_data['downloads']:
		clprint('blue','\t'+download['name']+' ('+str(download['size'])+' bytes)');
		cmd='cd '+tmp_dir+'/_downloads && wget --no-check-certificate '+download['html_url']+' 2>/dev/null'
		if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
		res=os.system(cmd);
		if not res==0:
			clprint ('red','Wget returned error code '+str(res))
			myexit(255)

# format data and save to files for user readable content
for key,data in gh_data.iteritems():
	txt=json.dumps(data,indent=3)
	f=open(tmp_dir+'/_textdump/'+key+'.json','w')
	f.write(txt)
	f.close()

# serialize object for use with restore script
txt=pickle.dumps(gh_data)
f=open(tmp_dir+'/github.repository.data.serialized','w')
f.write(txt)
f.close()

# create archive
if archive_type=='7z':
	clprint('blue','Creating 7zip archive');
	dst_file=backup_dir+'/github_repo_'+gh_repo+'_'+time.strftime('%Y%m%d_%H%M%S')+'.7z'
	cmd='cd '+tmp_dir+' && 7z a -r '+dst_file+' . >/dev/null'
else:
	clprint('blue','Creating tar archive');
	dst_file=backup_dir+'/github_repo_'+gh_repo+'_'+time.strftime('%Y%m%d_%H%M%S')+'.tgz'
	cmd='cd '+tmp_dir+' && tar -czf '+dst_file+' . >/dev/null'

if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
res=os.system(cmd);
if not res==0:
	clprint ('red','Error while creating archive '+str(res))
	myexit(255)

clprint('green','Archive created -> '+dst_file)

print
clprint('yellow','Warning!')
clprint('yellow','Be aware that some informations can\'t be restored:')
clprint('yellow','  - information about forks')
clprint('yellow','  - owner')
clprint('yellow','  - teams privileges')
clprint('yellow','  - pull requests')
clprint('yellow','  - watchers')
clprint('yellow','  - repository/issue events')
clprint('yellow','  - original elements id (not important)')
clprint('yellow','  - original elements creators')
clprint('yellow','  - original creation/update times of most elements')
clprint('yellow','  - downloads counts')

myexit(0)
