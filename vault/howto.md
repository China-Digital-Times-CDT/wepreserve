---
id: iu6nr9qel896bjhbckfl05d
title: How To Archive and Replay
desc: ''
updated: 1650534452370
created: 1648539827519
---


## Archive single pages

- Internet Archive (https://archive.org/web/)
    - We strongly suggest your installing [the Internet Archive plugin for browsers](https://github.com/internetarchive/wayback-machine-webextension) to save any web pages handily. 
- Webrecorder Archive (https://webrecorder.net/tools#archivewebpage)

## Archive the whole site

If you are a developer, you can run up this docker container(https://github.com/webrecorder/browsertrix-crawler) to save a web site as a whole. The saved site will be compressed into a single file as a snapshot from the specific date(time). The file is in a popular compression format called [WACZ](https://webrecorder.github.io/wacz-spec/1.1.1/). 


## Replay the artifacts

- Download the artifact above(caution: it's a large file)

Download the artifact file,normal in the format of .wacz, then put into a local folder(Alert: the file could be a huge one up to xx GB). 

- Open ReplayWeb (https://replayweb.page)

Once it downloaded, you can use the following link to replay the sites: https://replayweb.page/. E.g.  


- View and search

Select the file you downloaded to view the whole site and search for specific content.




