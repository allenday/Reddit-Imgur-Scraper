#!/usr/bin/env python3
# encoding: utf-8

import praw
import argparse
import urllib.request
import os
from imguralbum import *
import re

def is_valid(thing):
    # Could make this a single boolean statement
    # but that's a maintenance nightmare.
    if not thing.is_self:
        if thing.over_18 and args.no_nsfw:
            return False
        if thing.score < args.score:
            return False
        if "imgur.com" in thing.url:
            return True

    return False

def get_urls(generator, args):
    urls = []
    for thing in generator:
        if is_valid(thing) and thing.url not in urls:
            urls.append(thing.url)
            if re.match(r".*album.*",thing.title):
                if len(thing.comments) > 0:
                    u = re.findall('((https?\:\/\/)?(?:www\.)?(?:m\.)?imgur\.com\/a\/\w+)',thing.comments[0].body)
                    if len(u) > 0:
                        if len(u[0]) > 0:
                            urls.append(u[0][0])
    return urls

def download_images(url, args):
    # Check if it's an album
    try:
        downloader = ImgurAlbumDownloader(url)
        id = re.findall(r"\/a\/(\w+)",url)

        if downloader.num_images > args.length:
            return

        if not args.quiet:
            def image_progress(index, image_url, dest):
                print('Downloading image {} of {} from album {} to {}'.format(index, downloader.num_images, url, dest))

            downloader.on_image_download(image_progress)
        print("album {}".format(url))
        downloader.save_images(args.output + "/" + id[0])
    except ImgurAlbumException as e:
        # Not an album, unfortunately.
        # or some strange error happened.
        if not e.msg.startswith("URL"):
            print(e.msg)
            return

        # Check if it's a silly url.
        m = re.match(r"(?:https?\:\/\/)?(?:www\.)?(?:m\.)?imgur\.com\/([a-zA-Z0-9]+)", url)
        image = ''
        image_url = ''
        if m:
            # we don't know the extension
            # so we have to rip it from the url
            # by reading the HTML, unfortunately.
            response = urllib.request.urlopen(url)
            if response.getcode() != 200:
                print("Image download failed: HTML response code {}".format(response.getcode()))
                return

            html = response.read()
            image = re.search('<img src="(\/\/i\.imgur\.com\/([a-zA-Z0-9]+\.(?:jpg|jpeg|png|gif)))"', html)
            if image:
                image_url = "http:" + image.group(1)
        else:
            image = re.match(r'(https?\:\/\/)?(?:www\.)?(?:m\.)?i\.imgur\.com\/([a-zA-Z0-9]+\.(?:jpg|jpeg|png|gif))', url)
            if image:
                image_url = image.group(0)


        if not image_url:
            print("Image url {} could not be properly parsed.".format(url, image))
            return

        if not os.path.exists(args.output):
            os.makedirs(args.output)

        p = os.path.join(args.output, image.group(2))

        if not args.quiet:
            print("Downloading image {} to {}".format(image_url, p))

        urllib.request.urlretrieve(image_url, p)





def redditor_retrieve(r, args):
    user = r.get_redditor(args.username)
    gen = user.get_submitted(sort=args.sort, limit=args.limit)

    links = get_urls(gen, args)
    for link in links:
        download_images(link, args)

def subreddit_retrieve(r, args):
    sub = r.subreddit(args.subreddit)
    method = getattr(sub, "{}".format(args.sort))
    #method = getattr(sub, "get_{}".format(args.sort))
    gen = method(limit=args.limit)
    links = get_urls(gen, args)
    for link in links:
        download_images(link, args)

def post_retrieve(r, args):
    submission_id = ""

    m = re.match(r"(?:https?\:\/\/)?(?:www\.)?reddit.com\/r\/(?P<sub>\w+)\/comments\/(?P<id>\w+).+", args.post)

    if m:
        submission_id = m.group("id")
    else:
        m = re.match(r"(?:https?\:\/\/)?redd\.it\/(?P<id>\w+)", args.post)
        if m:
            submission_id = m.group("id")

    submission = r.get_submission(submission_id = submission_id)

    if(is_valid(submission)):
        download_images(submission.url, args)
    else:
        print("Invalid URL given: {}".format(submission.url))


if __name__ == "__main__":
    user_agent = "Image retriever 1.0.0 by /u/Rapptz"
    r = praw.Reddit(user_agent=user_agent)
    parser = argparse.ArgumentParser(description="Downloads imgur images from a user, subreddit, and/or post.",
                                     usage="%(prog)s [options...]")
    parser.add_argument("--username", help="username to scrap and download from", metavar="user")
    parser.add_argument("--subreddit", help="subreddit to scrap and download from", metavar="sub")
    parser.add_argument("--post", help="post to scrap and download from", metavar="url")

    parser.add_argument("--sort", help="choose the sort order for submissions (default: new)", 
                                  choices=["hot", "new", "controversial", "top"], metavar="type", default="new")

    parser.add_argument("--limit", type=int, help="number of submissions to look for (default: 100)",
                                   default=100, metavar="num")

    parser.add_argument("-q", "--quiet", action="store_true", help="doesn't print image download progress")
    parser.add_argument("-o", "--output", help="where to output the downloaded images", metavar="", default=".")
    parser.add_argument("--no-nsfw", action="store_true", help="only downloads images not marked nsfw")

    parser.add_argument("--score", help="minimum score of the image to download (default: 1)", type=int, 
                                   metavar="num", default=1)

    parser.add_argument("-l", "--length", help="skips album downloads over this length (default: 30)", type=int,
                                          default=30, metavar="num")

    args = parser.parse_args()

    if args.username:
        redditor_retrieve(r, args)

    if args.subreddit:
        subreddit_retrieve(r, args)

    if args.post:
        post_retrieve(r, args)
