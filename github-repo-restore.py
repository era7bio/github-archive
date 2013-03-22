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
	if tmp_dir!='' and os.path.isdir(tmp_dir) and tmp_dir!='/':
		os.system('rm -rf '+tmp_dir)
	if code>0 and gh_restored!={}:
		print
		clprint('red','Repository has already been created. Due to errors during restore, you should remove it manually.')
	sys.exit(code)
# ----------------------------------------
def signal_handler(signal,frame):
	print
	clprint('yellow','Ctrl-C pressed')
	myexit(254)
# ----------------------------------------

# init
import ConfigParser, sys, signal, os, re, urllib2, json, warnings, getpass, pickle

signal.signal(signal.SIGINT, signal_handler)
warnings.filterwarnings("ignore", category=RuntimeWarning)

currdir=os.getcwd()

debug=False
gh_user=''
gh_pass=''
gh_org=''
gh_repo=''
gh_backup_file=''
gh_restored={}
gh_backup={}

# parse config
config = ConfigParser.RawConfigParser()
config.read(__file__[:-3]+'.cfg')

def_gh_user=config.get('settings','def_gh_user')
def_gh_org=config.get('settings','def_gh_org')

hostname=config.get('settings','hostname')

tmp_dir=config.get('settings','tmp_dir')
if not os.path.isdir(tmp_dir):
	clprint('red','Temp directory ('+tmp_dir+') doesn\'t exist. Edit '+__file__+'.cfg file.')
	myexit(255)
tmp_dir+='/'+os.path.basename(os.tmpnam()).replace('file','dir')

os.makedirs(tmp_dir);

# load ssh pub key
try:
	ssh_key=open(config.get('settings','ssh_pub_key_file'),'r').read()
except:
	clprint('red','Cannot load ssh key ('+config.get('settings','ssh_pub_key_file')+'). Edit '+__file__+'.cfg file.')
	myexit(255)

# welcome
print
clprint ('green','Restore github repository from backup')

# show warning
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
print

# gather user input
while gh_user=='':
	gh_user=raw_input('Enter github user name or press \'enter\' for default ['+def_gh_user+']: ')

	if gh_user=='' :
		gh_user=def_gh_user
	if not re.search('^[a-z0-9\_\-\.]+$',gh_user,re.I) :
		clprint ('red','\tWrong user name. Allowed chars are letters, digits and \'-_.\'')
		gh_user=''

while gh_pass=='':
	gh_pass=getpass.getpass('Enter github user password: ')

	if gh_pass=='' :
		clprint ('red','\tPassword can\'t be empty')

while gh_org=='':
	gh_org=raw_input('Enter github organization (\'-\' for none) or press \'enter\' for default ['+def_gh_org+']: ')

	if gh_org=='':
		gh_org=def_gh_org
	if not re.search('^[a-z0-9\_\-\.]+$',gh_user,re.I) :
		clprint ('red','\tWrong organization name. Allowed chars are letters, digits and \'-_.\'')
		gh_org=''

while gh_backup_file=='':
	gh_backup_file=raw_input('Enter github backup file: ')

	if gh_backup_file=='' or not os.path.isfile(gh_backup_file) :
		clprint ('red','\tWrong backup file name')
		gh_backup_file=''

# check credenials
clprint('blue','Checking credentials');
res=gh_request_arr('users/user')
if res[0]==401:
	clprint ('red','Wrong user name or password')
	myexit(255)

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

# unpack data from archive
archive_type=''
if re.search('\.7z$',gh_backup_file,re.I): archive_type='7z'
elif re.search('\.tgz$',gh_backup_file,re.I): archive_type='tgz'
else:
	clprint ('red','Unknown archive extenstion')
	myexit(255)

if archive_type=='7z':
	clprint('blue','Unpacking 7z archive');
	cmd='cd '+tmp_dir+' && 7z x '+gh_backup_file+' >/dev/null'
else:
	clprint('blue','Unpacking tar archive');
	cmd='cd '+tmp_dir+' && tar -xzf '+gh_backup_file+' >/dev/null'

if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
res=os.system(cmd);
if not res==0:
	clprint ('red','Error while unpacking archive '+str(res))
	myexit(255)

# load data
try:
	f=open(tmp_dir+'/github.repository.data.serialized','r')
except:
	clprint ('red','Cannot load repository data')
	myexit(255)

txt=f.read()
f.close()
gh_backup=pickle.loads(txt)

if gh_backup['backup']['version']!=1:
	print
	clprint('yellow','Warning! Backup format is in version '+str(gh_backup['backup']['version'])+". This script handles version 1 only!")

# show backup info
print
clprint('green','Backup information:')
clprint('green','  - creation date:\t'+gh_backup['backup']['date'])
clprint('green','  - creator:\t\t'+gh_backup['backup']['user'])
clprint('green','  - organization:\t'+gh_backup['backup']['organization'])
clprint('green','  - repository name:\t'+gh_backup['backup']['repository'])
clprint('green','  - repository owner:\t'+gh_backup['repo']['owner']['login'])
clprint('green','  - size:\t\t'+str(gh_backup['repo']['size']))
clprint('green','  - private:',nonl=True)
if gh_backup['repo']['private']: clprint('yellow','\t\tyes')
else: clprint('green','\t\tno')
print

##############
while gh_repo=='':
	gh_repo=raw_input('Enter destination github repository name or press \'enter\' for original one ['+gh_backup['backup']['repository']+']: ')

	if gh_repo=='':
		gh_repo=gh_backup['backup']['repository']
	if not re.search('^[a-z0-9\_\-\.]+$',gh_repo,re.I) :
		clprint ('red','\tWrong repository name. Allowed chars are letters, digits and \'-_.\'')
		gh_repo=''

# check if repo exists
clprint('blue','Checking if repository exists');
if gh_org!='-':
	gh_repo_url='repos/'+gh_org+'/'+gh_repo
else:
	gh_repo_url='repos/'+gh_user+'/'+gh_repo

res=gh_request_arr(gh_repo_url)
if res[0]!=404 and res[1]['name']!='':
	clprint ('red','Repository '+gh_repo+' already exists')
	myexit(255)

# create repository
clprint('blue','Create new repository');
data={
	'name':gh_repo,
	'description':gh_backup['repo']['description'],
	'homepage':gh_backup['repo']['homepage'],
	'private':gh_backup['repo']['private'],
	'has_issues':gh_backup['repo']['has_issues'],
	'has_wiki':gh_backup['repo']['has_wiki'],
	'has_downloads':gh_backup['repo']['has_downloads']
}

data=json.JSONEncoder().encode(data)

if gh_org!='-':
	url='user/'+gh_org+'/repos'
else:
	url='user/repos'

res=gh_request_arr(url,data)
if res[0]==200:
	gh_restored['repo']=res[1]
elif res[0]==422:
	clprint ('red','Error ['+str(res[0])+'] while creating repository - '+res[1]['errors'][0]['message'])
	myexit(255);
else:
	clprint ('red','Error ['+str(res[0])+'] while creating repository')
	myexit(255);

# add ssh key
data={'title':hostname,'key':ssh_key}
data=json.JSONEncoder().encode(data)

clprint('blue','Adding deploy ssh key');
res=gh_request_arr(gh_repo_url+'/keys',data)
if res[0]==422:
	clprint ('yellow','\tKey already used');
	gh_restored['new_key']=0
else:
	gh_restored['new_key']=res[1]

# restore repositories
clprint('blue','Restoring main repository to github');
cmd='cd '+tmp_dir+'/'+gh_backup['backup']['repository']+' && git remote set-url origin '+gh_restored['repo']['ssh_url']+' && git push >/dev/null'
if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
res=os.system(cmd);
if not res==0:
	clprint ('red','Command returned error code '+str(res))
	myexit(255)	
	
if gh_backup['repo']['has_wiki']==1:
	clprint('blue','Creating wiki in github');
	res=gh_request_raw(gh_restored['repo']['html_url']+'/wiki')
	if res[0]==200 or res[0]==406:
		clprint('blue','Restoring wiki repository to github');
		cmd='cd '+tmp_dir+'/'+gh_backup['backup']['repository']+'.wiki && git remote set-url origin '+re.sub('\.git$','.wiki.git',gh_restored['repo']['ssh_url'])+' && git push >/dev/null'
		if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
		res=os.system(cmd);
		if not res==0:
			clprint ('red','Command returned error code '+str(res))
			myexit(255)
	else:
		clprint ('red','Error ['+str(res[0])+'] while creating wiki')
		myexit(255);
	
# remove ssh key
if gh_restored['new_key']:
	clprint('blue','Removing deploy ssh key');
	res=gh_request_raw(gh_repo_url+'/keys/'+str(gh_restored['new_key']['id']),data,method='DELETE')
del gh_restored['new_key']


# restore repo keys
if len(gh_backup['keys'])>0:
	clprint('blue','Restoring repository ssh keys');
	for key in gh_backup['keys']:
		data={'title':key['title'],'key':key['key']}
		data=json.JSONEncoder().encode(data)

		res=gh_request_arr(gh_repo_url+'/keys',data)
		if res[0]==422:
			clprint ('yellow','\tKey \''+key['title']+'\' ('+key['key'][0:28]+'.....'+key['key'][-20:]+') already used');
		elif res[0]!=200:
			clprint ('red','Error ['+str(res[0])+'] while adding key')
			myexit(255);
else:
	clprint('blue','No repository ssh keys');

if len(gh_backup['collaborators'])>0:
	clprint('blue','Restoring repository collaborators');
	for col in gh_backup['collaborators']:
		
		if col['login']==gh_restored['repo']['owner']['login']: continue
		
		clprint('blue','\t'+col['login']+' -',nonl=True)
		res=gh_request_raw(gh_repo_url+'/collaborators/'+col['login'],method='PUT')

		if res[0]==200:
			clprint ('blue','OK');
		else:
			clprint ('red','error ['+str(res[0])+'] while adding collaborator')
			myexit(255);
else:
	clprint('blue','No repository collaborators');

# restore hooks
if len(gh_backup['hooks'])>0:
	clprint('blue','Restoring repository hooks');
	for hook in gh_backup['hooks']:

		data={
			'name':hook['name'],
			'config':hook['config'],
			'events':hook['events'],
			'active':hook['active']
		}
		data=json.JSONEncoder().encode(data)
		
		clprint('blue','\t'+hook['name']+' -',nonl=True)
		res=gh_request_arr(gh_repo_url+'/hooks',data)
		if res[0]==200:
			clprint ('blue','OK');
		else:
			clprint ('red','error ['+str(res[0])+'] while adding hook')
			myexit(255);
else:
	clprint('blue','No repository hooks');

# restore labels
if len(gh_backup['labels'])>0:
	clprint('blue','Restoring repository labels');
	for label in gh_backup['labels']:

		data={
			'name':label['name'],
			'color':label['color']
		}
		data=json.JSONEncoder().encode(data)
		
		clprint('blue','\t'+label['name']+' -',nonl=True)
		res=gh_request_arr(gh_repo_url+'/labels',data)
		if res[0]==200:
			clprint ('blue','OK');
		elif res[0]==422:
			clprint ('yellow','already exists');
		else:
			clprint ('red','error ['+str(res[0])+'] while adding label')
			myexit(255);
else:
	clprint('blue','No repository labels');

# restore milestones
if len(gh_backup['milestones'])>0:
	milestones=sorted(gh_backup['milestones'],key=lambda x: (x['number']))
	clprint('blue','Restoring repository milestones');
	for milestone in milestones:

		data={
			'title':milestone['title'],
			'state':milestone['state'],
			'description':milestone['description'],
			'due_on':milestone['due_on']
		}
		data=json.JSONEncoder().encode(data)
		
		clprint('blue','\t\''+milestone['title']+'\' -',nonl=True)
		res=gh_request_arr(gh_repo_url+'/milestones',data)
		if res[0]==200:
			clprint ('blue','OK');
		else:
			clprint ('red','error ['+str(res[0])+'] while adding milestones')
			myexit(255);
	del milestone,milestones
else:
	clprint('blue','No repository milestones');

# restore issues
if len(gh_backup['issues'])>0:
	issues=sorted(gh_backup['issues'],key=lambda x: (x['number']))
	clprint('blue','Restoring repository issues & comments');
	for issue in issues:
		data={
			'title':issue['title'],
			'body':issue['body'],
			'assignee':issue['assignee'],
			'labels':issue['labels']
		}
		if issue['milestone'].__class__.__name__=='dict':
			data['milestone']=issue['milestone']['number']

		data=json.JSONEncoder().encode(data)
		
		clprint('blue','\t\''+issue['title']+'\' -',nonl=True)
		res=gh_request_arr(gh_repo_url+'/issues',data)
		if res[0]==200:
			if issue['state']=='closed':
				new_issue=res[1]
				data={
					'state':'closed'
				}
				data=json.JSONEncoder().encode(data)
				res=gh_request_raw(new_issue['url'],data,method='PATCH')
				if res[0]==200:
					clprint ('blue','OK');
				else:
					clprint ('red','error ['+str(res[0])+'] while adding issue')
					myexit(255);			
				del new_issue
		else:
			clprint ('red','error ['+str(res[0])+'] while adding issue')
			myexit(255);

		if len(gh_backup['comments'][issue['number']])>0:
			clprint ('blue','\t\tcomments -',nonl=True);
			comments=gh_backup['comments'][issue['number']]
			comments=sorted(comments,key=lambda x: (x['id']))
			for comment in comments:
				data={
					'body':comment['body']
				}
				data=json.JSONEncoder().encode(data)
				res=gh_request_raw(gh_repo_url+'/issues/'+str(issue['number'])+'/comments',data)
				if res[0]!=200:
					clprint ('red','error ['+str(res[0])+'] while adding comment')
					myexit(255);
			clprint ('blue','OK');
			del comment,comments
	
	del issue,issues
else:
	clprint('blue','No repository issues');

# restore downloads
if len(gh_backup['downloads'])>0:
	clprint('blue','Restoring repository downloads');
	for download in gh_backup['downloads']:

		data={
			'name':download['name'],
			'size':download['size'],
			'description':download['description'],
			'content_type':download['content_type']
		}
		data=json.JSONEncoder().encode(data)
		
		clprint('blue','\t'+download['name']+' ('+str(download['size'])+' bytes) -',nonl=True)
		res=gh_request_arr(gh_repo_url+'/downloads',data)
		if res[0]==200:
			newdownload=res[1]
			clprint('blue','uploading -',nonl=True)

			cmd='curl -F "key='+newdownload['path']+'" -F "acl='+newdownload['acl']+'" -F "success_action_status=201" -F "Filename='+newdownload['name']+'" -F "AWSAccessKeyId='+newdownload['accesskeyid']+'" -F "Policy='+newdownload['policy']+'" -F "Signature='+newdownload['signature']+'" -F "Content-Type='+newdownload['mime_type']+'" -F "file=@'+tmp_dir+'/_downloads/'+download['name']+'" https://github.s3.amazonaws.com/ >/dev/null 2>/dev/null'
			if debug: clprint('cyan','DEBUG: system cmd: '+cmd)
			res=os.system(cmd);
			if not res==0:
				clprint ('red','curl error ['+str(res)+'] during upload')
				myexit(255)
			else:
				clprint ('blue','OK');
		else:
			clprint ('red','error ['+str(res[0])+'] while adding download')
			myexit(255);
else:
	clprint('blue','No repository downloads');

myexit(0)

