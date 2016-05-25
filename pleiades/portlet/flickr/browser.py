import logging
from random import choice
from urllib import urlencode

import httplib2
import simplejson

from Acquisition import aq_inner, aq_parent
from plone.memoize.instance import memoize
from Products.CMFCore.utils import getToolByName
from zope.interface import implements, Interface, Attribute
from zope.publisher.browser import BrowserPage, BrowserView

from Products.PleiadesEntity.content.interfaces import ILocation, IName, IPlace

log = logging.getLogger("pleiades.portlet.flickr")

FLICKR_API_ENDPOINT = "https://api.flickr.com/services/rest/"
FLICKR_API_KEY = "b5899a9f7069f933b46b32b949ab4afd"
FLICKR_TAGS_BASE = "https://www.flickr.com/photos/tags/"
PLEIADES_PLACES_ID = "1876758@N22"
IMG_TMPL = "https://farm%(farm)s.staticflickr.com/%(server)s/%(id)s_%(secret)s_m.jpg"
PAGE_TMPL = "https://flickr.com/photos/%(owner)s/%(id)s/in/pool-1876758@N22"


class RelatedFlickrJson(BrowserView):

    """Makes two Flickr API calls and writes the number of related
    photos and URLs for the most viewed related photo from the Pleiades
    Places group to JSON like

    {"portrait": {
      "page": 
        "http://flickr.com/photos/27621672@N04/3734425631/in/pool-1876758@N22", 
       "img": "http://farm3.staticflickr.com/2474/3734425631_b15979f2cd_m.jpg", 
       "title": "Pont d'Ambroix by sgillies" }, 
     "related": {
       "url": ["http://www.flickr.com/photos/tags/pleiades:*=149492/"], 
       "total": 2 }}

    for use in the Flickr Photos portlet on every Pleiades place page.
    """

    def __call__(self, **kw):
        data = {}
        context = self.context
        
        if IPlace.providedBy(context):
            pid = context.getId() # local id like "149492"
        elif ILocation.providedBy(context) or IName.providedBy(context):
            pid = aq_parent(aq_inner(context)).getId()
        else:
            pid = "*"
        
        # Count of related photos

        tag = "pleiades:*=" + pid

        h = httplib2.Http()
        q = dict(
            method="flickr.photos.search",
            api_key=FLICKR_API_KEY,
            machine_tags="pleiades:*=%s" % pid,
            format="json",
            nojsoncallback=1 )
        
        resp, content = h.request(FLICKR_API_ENDPOINT + "?" + urlencode(q), "GET")
        
        if resp['status'] == "200":
            total = 0
            photos = simplejson.loads(content).get('photos')
            if photos:
                total = int(photos['total'])

            data['related'] = dict(total=total, url=FLICKR_TAGS_BASE + tag)
        
        # Get portrait photo from group pool

        h = httplib2.Http()
        q = dict(
            method="flickr.groups.pools.getPhotos",
            api_key=FLICKR_API_KEY,
            group_id=PLEIADES_PLACES_ID,
            extras="views",
            format="json",
            nojsoncallback=1 )
        
        if pid != "*":
            q['tags'] = "pleiades:depicts=" + pid

        resp, content = h.request(FLICKR_API_ENDPOINT + "?" + urlencode(q), "GET")
        
        if resp['status'] == '200':
            total = 0
            photos = simplejson.loads(content).get('photos')
            if photos:
                total = int(photos['total'])
            if total < 1:
                data['portrait'] = None
            else:
                # Sort found photos by number of views, descending
                most_viewed = sorted(
                    photos['photo'], key=lambda p: p['views'], reverse=True )
                if pid == "*":
                    photo = choice(most_viewed)
                else:
                    photo = most_viewed[0]

                title = "%s by %s." % (
                    photo['title'].rstrip(" ."), photo['ownername'] )
                data['portrait'] = dict(
                    title=title, img=IMG_TMPL % photo, page=PAGE_TMPL % photo )
        
        self.request.response.setStatus(resp['status'])
        self.request.response.setHeader('Content-Type', 'application/json')
        return simplejson.dumps(data)
