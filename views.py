# -*- coding: utf-8 -*-"""

"""
Django views for wip application of wip project.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/db/models/
"""
import sys
"""
sys.stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stderr = codecs.getwriter('utf8')(sys.stderr)
"""
reload(sys)  
sys.setdefaultencoding('utf8')
import os
import datetime

import logging
logger = logging.getLogger('wip')

import re
from math import sqrt
from lxml import html, etree
import json

from settings import USE_SCRAPY, USE_NLTK
from haystack.query import SearchQuerySet
# from search_indexes import StringIndex
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.db import connection
# from django.db.models import Q, Count
from django.db.models.expressions import RawSQL, Q
from django import forms
from django.contrib import messages
from actstream import action, registry

from models import Language, Site, Proxy, Webpage, PageVersion, TranslatedVersion
from models import Block, BlockEdge, TranslatedBlock, BlockInPage, String, Txu, TxuSubject #, TranslatedVersion
from models import segments_from_string, non_invariant_words
from models import STRING_TYPE_DICT, UNKNOWN, SEGMENT #, TERM, FRAGMENT
from models import TEXT_ASC # , ID_ASC, DATETIME_DESC, DATETIME_ASC
from models import TO_BE_TRANSLATED, TRANSLATED, PARTIALLY, INVARIANT, ALREADY
from models import MYMEMORY, TRANSLATION_SERVICE_DICT
from forms import SiteManageForm, ProxyManageForm, PageEditForm, PageSequencerForm, BlockEditForm, BlockSequencerForm
from forms import StringSequencerForm, StringEditForm, StringsTranslationsForm, StringTranslationForm, TranslationServiceForm, FilterPagesForm
from session import get_language, set_language, get_site, set_site

from settings import PAGE_SIZE, PAGE_STEPS
from settings import DATA_ROOT, RESOURCES_ROOT, tagger_filename, BLOCK_TAGS, QUOTES, SEPARATORS, STRIPPED, DEFAULT_STRIPPED, EMPTY_WORDS, PAGES_EXCLUDE_BY_CONTENT
from utils import strings_from_html, elements_from_element, block_checksum, ask_mymemory, text_to_list # , non_invariant_words
import srx_segmenter

registry.register(Site)
registry.register(Proxy)
registry.register(Webpage)
registry.register(PageVersion)
registry.register(TranslatedVersion)
registry.register(Block)
registry.register(TranslatedBlock)
#     action.send(user, verb='Create', action_object=forum, target=project)

def robots(request):
    response = render_to_response('robots.txt', {}, context_instance=RequestContext(request))
    response['Content-Type'] = 'text/plain; charset=utf-8'
    return response

def empty_page(request):
    response = render_to_response('robots.txt', {}, context_instance=RequestContext(request))
    response['Content-Type'] = 'text/plain; charset=utf-8'
    return response

def steps_before(page):
    steps = list(PAGE_STEPS)
    steps.reverse()
    steps = [page-step for step in steps if page-step >= 1 and page-step < page]
    if page > 1 and steps[0] > 1:
        steps = [1] + steps
    return steps

def steps_after(page, page_count):
    steps = [page+step for step in PAGE_STEPS if page+step > page and page+step <= page_count]
    if page < page_count and steps[-1] < page_count:
        steps.append(page_count)
    return steps

def home(request):
    user = request.user
    var_dict = {}
    var_dict['original_sites'] = original_sites = Site.objects.all().order_by('name')
    sites = []
    for site in original_sites:
        site_dict = {}
        site_dict['name'] = site.name
        site_dict['slug'] = site.slug
        site_dict['source_pages'] = Webpage.objects.filter(site=site)
        site_dict['page_versions'] = PageVersion.objects.filter(webpage__site=site)
        site_dict['translated_versions'] = TranslatedVersion.objects.filter(webpage__site=site)
        site_dict['source_blocks'] = Block.objects.filter(site=site)
        site_dict['translated_blocks'] = TranslatedBlock.objects.filter(block__site=site)
        proxies = site.get_proxies()
        site_dict['proxies'] = proxies
        sites.append(site_dict)
    var_dict['sites'] = sites
    return render_to_response('homepage.html', var_dict, context_instance=RequestContext(request))

def language(request, language_code):
    set_language(request, language_code or '')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

def sites(request):
    var_dict = {}
    sites = Site.objects.all().order_by('name')
    var_dict['sites'] = sites
    return render_to_response('sites.html', var_dict, context_instance=RequestContext(request))

def proxies(request):
    var_dict = {}
    proxies = Proxy.objects.all().order_by('site__name')
    var_dict['proxies'] = proxies
    return render_to_response('proxies.html', var_dict, context_instance=RequestContext(request))

"""
def text_to_list(text):
    list = text.splitlines()
    list = [item.strip() for item in list]
    return [item for item in list if len(item)]
"""
    
def site(request, site_slug):
    user = request.user
    site = get_object_or_404(Site, slug=site_slug)
    set_site(request, site_slug)
    var_dict = {}
    var_dict['site'] = site
    var_dict['can_manage'] = site.can_manage(user)
    var_dict['can_operate'] = site.can_operate(user)
    var_dict['can_view'] = site.can_view(user)
    var_dict['proxies'] =  proxies = site.get_proxies()
    var_dict['proxy_languages'] = proxy_languages = [proxy.language for proxy in proxies]
    post = request.POST
    if post:
        site_crawl = post.get('site_crawl', '')
        extract_blocks = post.get('extract_blocks', '')
        refetch_pages = post.get('refetch_pages', '')
        extract_segments = post.get('extract_segments', '')
        download_segments = post.get('download_segments', '')
        import_invariants = post.get('import_invariants', '')
        apply_invariants = post.get('apply_invariants', '')
        delete_site = post.get('delete_site', '')
        guess_blocks_language = post.get('guess_blocks_language', '')
        # form = SiteManageForm(post)
        form = SiteManageForm(post, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            if site_crawl:
                clear_pages = data['clear_pages']
                if clear_pages:
                    Webpage.objects.filter(site=site).delete()
                t = crawl_site.delay(site.id)
                print 'site_crawl : ', site.name, 'task id: ', t
            elif extract_blocks:
                clear_blocks = data['clear_blocks']
                if clear_blocks:
                    Block.objects.filter(site=site).delete()
                    BlockInPage.objects.filter(block__site=site).delete()
                    BlockEdge.objects.filter(parent__site=site).delete()
                webpages = Webpage.objects.filter(site=site).exclude(no_translate=True)
                extract_deny_list = text_to_list(site.extract_deny)
                translate_deny_list = text_to_list(site.translate_deny)
                for webpage in webpages:
                    if webpage.last_unfound and (webpage.last_unfound > webpage.last_checked):
                        continue
                    should_skip = False
                    path = webpage.path
                    for deny_path in extract_deny_list:
                        if path.count(deny_path):
                            should_skip = True
                            break
                    if should_skip:
                        continue
                    should_skip = False
                    for deny_path in translate_deny_list:
                        if path.count(deny_path):
                            should_skip = True
                            break
                    if should_skip:
                        continue
                    # try:
                    if True:
                        n_1, n_2, n_3 = webpage.extract_blocks()
                        webpage.create_blocks_dag()
                    # except:
                    else:
                        print 'extract_blocks: error on page ', webpage.id
            elif refetch_pages:
                n_pages, n_updates, n_unfound = site.refetch_pages()
                messages.add_message(request, messages.INFO, 'Requested %d pages: %d updated, %d unfound' % (n_pages, n_updates, n_unfound))
            elif extract_segments or download_segments:
                segmenter = site.make_segmenter()
                dry = False
                language = site.language
                language_code = language.code
                webpages = Webpage.objects.filter(site=site)
                extract_deny_list = text_to_list(site.extract_deny)
                if dry:
                    print extract_deny_list
                if download_segments:
                    download_list = []
                for webpage in webpages:
                    path = webpage.path
                    if webpage.last_unfound and (webpage.last_unfound > webpage.last_checked):
                        continue
                    should_skip = False
                    for deny_path in extract_deny_list:
                        if path.count(deny_path):
                            should_skip = True
                            break
                    if should_skip:
                        continue
                    page_versions = PageVersion.objects.filter(webpage=webpage).order_by('-time')
                    if not page_versions:
                        continue
                    page_version = page_versions[0]
                    skip_page = False
                    for content in PAGES_EXCLUDE_BY_CONTENT.get(site.slug, []):
                        # if page_version.body.count(content):
                        if len(path)>1 and page_version.body.count(content):
                            skip_page = True
                            break
                    if skip_page:
                        continue
                    """
                    try:
                        segments = page_version.page_version_get_segments()
                    except: # Unicode strings with encoding declaration are not supported. Please use bytes input or XML fragments without declaration.
                        print '- error on ', path
                        continue
                    """
                    segments = page_version.page_version_get_segments(segmenter=segmenter)
                    if dry:
                        print path
                        continue
                    for s in segments:
                        """ THESE FILTERS HAVE BEEN POOLED IN THE models.segments_from_string FUNCTION
                        s = s.replace('\xc2\xa0', ' ')
                        if not s: continue
                        # s = s.strip(SEPARATORS[language_code])
                        s = s.strip()
                        if not s: continue
                        for left, right in QUOTES:
                            if s[0]==left and s.count(right)<=1:
                                s = s[1:]
                                if not s: break
                                s = s.replace(right, '').strip()
                                if not s: break
                            if s[-1]==right and s.count(left)<=1:
                                s = s[:-1]
                                if not s: break
                                s = s.replace(right, '').strip()
                                if not s: break
                        if not s: continue
                        words = re.split(" |\'", s)
                        if len(words) > 1:
                            stripped = False
                            while words and can_strip(words[0]):
                                words = words[1:]
                                stripped = True
                            while words and can_strip(words[-1]):
                                words = words[:-1]
                                stripped = True
                            if not words: continue
                            if stripped:
                                s = ' '.join(words)
                        if len(words) == 1:
                            word = words[0]
                            if can_strip(word) or word.isupper() or word.lower() in EMPTY_WORDS[language_code]:
                                continue
                        if s.startswith('Home'):
                            continue
                        """
                        if download_segments:
                            if not s in download_list:
                                download_list.append(s)
                        else:
                            is_model_instance, string = get_or_add_string(request, s, language, string_type=SEGMENT, add=True, txu=None, site=site, reliability=0)
                        sys.stdout.write('.')
                if download_segments:
                    # messages.add_message(request, messages.INFO, 'Downloaded %d segments.' % len(download_list))
                    data = u'\r\n'.join(download_list)
                    response = HttpResponse(data, content_type='application/octet-stream')
                    time_stamp = datetime.datetime.now().strftime('%y%m%d-%H-%M-%S')
                    filename = u'%s-segments.%s.txt' % (site.slug, time_stamp)
                    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
                    return response
            elif delete_site:
                delete_confirmation = data['delete_confirmation']
                if delete_confirmation:
                    site.delete()
                    return HttpResponseRedirect('/')
            elif import_invariants:
                language = site.language
                clear_invariants = data['clear_invariants']
                if clear_invariants:
                    strings = String.objects.filter(invariant=True, site=site)
                    for string in strings:
                        string.delete()
                f = request.FILES.get('file', None)
                if f:
                    i = 0
                    m = 0
                    n = 0
                    d = 0
                    for line in f:
                        line = line.strip()
                        i += 1
                        if line:
                            m += 1
                            try:
                                if String.objects.filter(site=site, text=line, invariant=True):
                                    d += 1
                                else:
                                    string = String(txu=None, language=language, site=site, text=line, reliability=0, invariant=True)
                                    string.save()
                                    n += 1
                            except:
                                print 'error: ', i
                    messages.add_message(request, messages.INFO, 'Imported %d invariants out of %d (%d repetitions).' % (n, m, d))
                else:
                    messages.add_message(request, messages.ERROR, 'Please, select a file to upload.')
            elif apply_invariants:
                blocks = Block.objects.filter(site=site, language__isnull=True, no_translate=False)
                if blocks:
                    """
                    srx_filepath = os.path.join(RESOURCES_ROOT, 'segment.srx')
                    srx_rules = srx_segmenter.parse(srx_filepath)
                    italian_rules = srx_rules['Italian']
                    segmenter = srx_segmenter.SrxSegmenter(italian_rules)
                    """
                    segmenter = site.make_segmenter()
                n_invariants = 0
                for block in blocks:
                    if block.apply_invariants(segmenter):
                        n_invariants += 1
                messages.add_message(request, messages.INFO, '%d blocks marked as invariant.' % n_invariants)
            elif guess_blocks_language:
                from wip.utils import guess_block_language
                blocks = Block.objects.filter(site=site, language__isnull=True)
                if proxy_languages:
                    proxy_codes = [l.code for l in proxy_languages]
                    for block in blocks:
                        if block.language_id or block.no_translate:
                            continue
                        code = guess_block_language(block)
                        if code in proxy_codes:
                            block.language_id = code
                            block.save()
            else:
                for key in post.keys():
                    if key.startswith('addproxy-'):
                        code = key.split('-')[1]
                        proxy = Proxy(site=site, language_id=code, name='%s %s' % (site.name, code.upper()), base_path='%s/%s' % (site.path_prefix, code))
                        proxy.save()
                        break
    missing_languages = Language.objects.exclude(code=site.language_id)
    missing_languages = missing_languages.exclude(code__in=[l.code for l in proxy_languages])
    var_dict['missing_languages'] = missing_languages
    webpages = Webpage.objects.filter(site=site).order_by('id')
    var_dict['page_count'] = page_count = webpages.count()
    var_dict['first_page'] = webpages and webpages[0] or None
    blocks = Block.objects.filter(site=site).order_by('id')
    var_dict['block_count'] = block_count = blocks.count()
    var_dict['first_block'] = blocks and blocks[0] or None
    pages, pages_total, pages_invariant, pages_proxy_list = site.pages_summary()
    var_dict['pages_total'] = pages_total
    var_dict['pages_invariant'] = pages_invariant
    var_dict['pages_proxy_list'] = pages_proxy_list
    blocks, blocks_total, blocks_invariant, blocks_proxy_list = site.blocks_summary()
    var_dict['blocks_total'] = blocks_total
    var_dict['blocks_invariant'] = blocks_invariant
    var_dict['blocks_proxy_list'] = blocks_proxy_list
    var_dict['manage_form'] = SiteManageForm()
    return render_to_response('site.html', var_dict, context_instance=RequestContext(request))
 
def proxy(request, proxy_slug):
    user = request.user
    proxy = get_object_or_404(Proxy, slug=proxy_slug)
    var_dict = {}
    var_dict['proxy'] = proxy
    var_dict['can_manage'] = proxy.can_manage(user)
    var_dict['can_operate'] = proxy.can_operate(user)
    var_dict['can_view'] = proxy.can_view(user)
    var_dict['site'] = site = proxy.site
    var_dict['language'] = language = proxy.language
    post = request.POST
    if post:
        print 'request.POST: ', post
        delete_pages = post.get('delete_pages', '')
        delete_blocks = post.get('delete_blocks', '')
        delete_proxy = post.get('delete_proxy', '')
        import_translations = post.get('import_translations', '')
        apply_tm = post.get('apply_tm', '')
        propagate_up = post.get('propagate_up', '')
        form = ProxyManageForm(post)
        if form.is_valid():
            data = form.cleaned_data
            if delete_pages:
                delete_pages_confirmation = data['delete_pages_confirmation']
                if delete_pages_confirmation:
                    TranslatedVersion.objects.filter(webpage__site=site, language=language).delete()
            elif delete_blocks:
                delete_blocks_confirmation = data['delete_blocks_confirmation']
                if delete_blocks_confirmation:
                    TranslatedBlock.objects.filter(block__site=site, language=language).delete()
            elif delete_proxy:
                delete_proxy_confirmation = data['delete_proxy_confirmation']
                if delete_proxy_confirmation:
                    proxy.delete()
                    messages.add_message(request, messages.INFO, 'Proxy deleted.')
                    return HttpResponseRedirect('/site/%s/' % site.slug)
            elif import_translations:
                f = request.FILES.get('file', None)
                if f:
                    m, n = proxy.import_translations(f, request=request)
                    messages.add_message(request, messages.INFO, '%d translations read, %d translations added.' % (m, n))
            elif apply_tm:
                n_ready, n_translated, n_partially = proxy.apply_translation_memory()
                messages.add_message(request, messages.INFO, 'TM applied to %d blocks: %d fully translated, %d partially translated.' % (n_ready, n_translated, n_partially))
            elif propagate_up:
                print 'propagate_up'
                n_new, n_updated, n_no_updated = proxy.propagate_up_block_updates()
                messages.add_message(request, messages.INFO, 'Up propagation: %d new, %d updated, %d not updated blocks' % (n_new, n_updated, n_no_updated))
    webpages = Webpage.objects.filter(site=site).order_by('id')
    var_dict['page_count'] = page_count = webpages.count()
    var_dict['first_page'] = webpages and webpages[0] or None
    blocks = Block.objects.filter(site=site).order_by('id')
    var_dict['block_count'] = block_count = blocks.count()
    var_dict['first_block'] = blocks and blocks[0] or None
    pages, pages_total, pages_invariant, pages_proxy_list = site.pages_summary()
    var_dict['pages_total'] = pages_total
    var_dict['pages_invariant'] = pages_invariant
    var_dict['pages_proxy_list'] = pages_proxy_list
    blocks, blocks_total, blocks_invariant, blocks_proxy_list = site.blocks_summary()
    var_dict['blocks_total'] = blocks_total
    var_dict['blocks_invariant'] = blocks_invariant
    var_dict['blocks_proxy_list'] = blocks_proxy_list
    
    var_dict['translated_pages_count'] = page_count = TranslatedVersion.objects.filter(webpage__site=site, language=language).count()
    # var_dict['translated_blocks_count'] = TranslatedBlock.objects.filter(block__site=site, language=language).count()
    var_dict['translated_blocks_count'] = translated_blocks_count = TranslatedBlock.objects.filter(block__site=site, state=TRANSLATED, language_id=proxy.language_id).count()
    var_dict['partially_blocks_count'] = partially_blocks_count = TranslatedBlock.objects.filter(block__site=site, state=PARTIALLY, language_id=proxy.language_id).count()
    var_dict['left_blocks_count'] = blocks_total - blocks_invariant - translated_blocks_count - partially_blocks_count
    var_dict['blocks_ready'] = blocks_ready = proxy.blocks_ready()
    var_dict['ready_count'] = len(blocks_ready)
    var_dict['manage_form'] = ProxyManageForm()
    return render_to_response('proxy.html', var_dict, context_instance=RequestContext(request))


def site_pages(request, site_slug):
    var_dict = {}
    site = get_object_or_404(Site, slug=site_slug)
    var_dict['site'] = site

    filter_pages_context = request.session.get('filter_pages_context', {})
    path_filter = filter_pages_context.get('path_filter', '')
    from_start = filter_pages_context.get('from_start', False)
    if request.method == 'POST':
        form = FilterPagesForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            filter_pages_context['path_filter'] = path_filter = data['path_filter']
            filter_pages_context['from_start'] = at_start = data['from_start']
            request.session['filter_pages_context'] = filter_pages_context
    else:
        form = FilterPagesForm(initial={ 'path_filter': path_filter, 'from_start': from_start, })
    var_dict['filter_pages_form'] = form

    var_dict['proxies'] =  proxies = Proxy.objects.filter(site=site)
    qs = Webpage.objects.filter(site=site)
    if path_filter:
        if from_start:
            qs = qs.filter(path__istartswith=path_filter)
        else:
            qs = qs.filter(path__icontains=path_filter)
    var_dict['page_count'] = page_count = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page = request.GET.get('page', 1)
    try:
        site_pages = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = 1
        site_pages = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.num_pages
        site_pages = paginator.page(paginator.num_pages)
    var_dict['page_size'] = PAGE_SIZE
    var_dict['page'] = page = int(page)
    var_dict['offset'] = (page-1) * PAGE_SIZE
    var_dict['before'] = steps_before(page)
    var_dict['after'] = steps_after(page, paginator.num_pages)
    var_dict['site_pages'] = site_pages
    return render_to_response('pages.html', var_dict, context_instance=RequestContext(request))

def page(request, page_id):
    var_dict = {}
    first_page = None
    if int(page_id) == 0:
        site_slug = request.GET.get('site', '')
        filter = request.GET.get('filter', '')
        if site_slug and filter:
            site = get_object_or_404(Site, slug=site_slug)
            webpages = Webpage.objects.filter(site=site)
            if filter == 'no_translate':
                webpages = webpages.filter(no_translate=True)
            if webpages:
                first_page = webpage = webpages.order_by('id')[0]
    else:
        webpage = get_object_or_404(Webpage, pk=page_id)
        var_dict['site'] = site = webpage.site
    var_dict['proxy_languages'] = proxy_languages = [proxy.language for proxy in site.get_proxies()]
    proxy_codes = [proxy.language_id for proxy in site.get_proxies()]
    var_dict['scans'] = PageVersion.objects.filter(webpage=webpage).order_by('-time')
    PageSequencerForm.base_fields['translation_languages'].queryset = Language.objects.filter(code__in=proxy_codes)
    save_page = apply_filter = goto = '' 
    post = request.POST
    if post:
        save_page = post.get('save_page', '')
        apply_filter = post.get('apply_filter', '')
        if not (save_page or apply_filter):
            for key in post.keys():
                if key.startswith('goto-'):
                    goto = int(key.split('-')[1])
                    webpage = get_object_or_404(Webpage, pk=goto)
        if save_page:
            form = PageEditForm(post)
            if form.is_valid():
                data = form.cleaned_data
                no_translate = data['no_translate']
                webpage.no_translate = no_translate
                webpage.save()
        elif (apply_filter or goto):
            form = PageSequencerForm(post)
            if form.is_valid():
                data = form.cleaned_data
                page_age = data['page_age']
                translation_state = int(data['translation_state'])
                translation_languages = data['translation_languages']
                translation_codes = [l.code for l in translation_languages]
                translation_age = data['translation_age']
                list_blocks = data['list_blocks']
    if not post or save_page:
        translation_state = None
        translation_codes = []
        if not post and first_page:
            if filter == 'no_translate':
                translation_state = INVARIANT
        sequencer_context = request.session.get('page_sequencer_context', {})
        if sequencer_context:
            page_age = sequencer_context.get('page_age', '')
            translation_state = translation_state or sequencer_context.get('translation_state', TO_BE_TRANSLATED)
            translation_codes = sequencer_context.get('translation_codes', [])
            translation_age = sequencer_context.get('translation_age', '')
            list_blocks = sequencer_context.get('list_blocks', False)
            request.session['page_sequencer_context'] = {}
        else:
            page_age = ''
            translation_state = translation_state or TO_BE_TRANSLATED
            translation_codes = [proxy.language.code for proxy in site.get_proxies()]
            translation_age = ''
            list_blocks = False
        translation_languages = translation_codes and Language.objects.filter(code__in=translation_codes) or []
    sequencer_context = {}
    sequencer_context['page_age'] = page_age
    sequencer_context['translation_state'] = translation_state
    sequencer_context['translation_codes'] = translation_codes
    sequencer_context['translation_age'] = translation_age
    sequencer_context['list_blocks'] = list_blocks
    request.session['page_sequencer_context'] = sequencer_context
    var_dict['webpage'] = webpage
    previous, next = webpage.get_navigation(translation_state=translation_state, translation_codes=translation_codes)
    var_dict['previous'] = previous
    var_dict['next'] = next
    var_dict['site'] = site
    if save_page or goto:
        return HttpResponseRedirect('/page/%d/' % webpage.id)        
    var_dict['edit_form'] = PageEditForm(initial={'no_translate': webpage.no_translate,})
    var_dict['sequencer_form'] = PageSequencerForm(initial={'page_age': page_age, 'translation_state': translation_state, 'translation_languages': translation_languages, 'translation_age': translation_age, 'list_blocks': list_blocks, })
    blocks, total, invariant, proxy_list = webpage.blocks_summary()
    # print total, invariant, proxy_list
    var_dict['blocks'] = blocks
    var_dict['list_blocks'] = list_blocks
    var_dict['total'] = total
    var_dict['block_count'] = total
    var_dict['invariant'] = invariant
    var_dict['proxy_list'] = proxy_list
    return render_to_response('page.html', var_dict, context_instance=RequestContext(request))

def page_blocks(request, page_id):
    var_dict = {}
    var_dict['webpage'] = webpage = get_object_or_404(Webpage, pk=page_id)
    var_dict['site'] = site = webpage.site
    # qs = webpage.blocks.all()
    qs = BlockInPage.objects.filter(webpage=webpage).order_by('xpath', 'time')
    var_dict['block_count'] = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page = request.GET.get('page', 1)
    try:
        page_blocks = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = 1
        page_blocks = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.num_pages
        page_blocks = paginator.page(paginator.num_pages)
    var_dict['page_size'] = PAGE_SIZE
    var_dict['page'] = page = int(page)
    var_dict['offset'] = (page-1) * PAGE_SIZE
    var_dict['before'] = steps_before(page)
    var_dict['after'] = steps_after(page, paginator.num_pages)
    var_dict['page_blocks'] = page_blocks
    return render_to_response('page_blocks.html', var_dict, context_instance=RequestContext(request))

def page_extract_blocks(request, page_id):
    webpage = get_object_or_404(Webpage, pk=page_id)
    webpage.extract_blocks()
    webpage.create_blocks_dag()
    return page(request, page_id)

def page_cache_translation(request, page_id, language_code):
    webpage = get_object_or_404(Webpage, pk=page_id)
    webpage.cache_translation(language_code)
    return page(request, page_id)

def page_proxy(request, page_id, language_code):
    page = get_object_or_404(Webpage, pk=page_id)
    content, has_translation = page.get_translation(language_code)
    if content:
        return HttpResponse(content, content_type="text/html")
    else:
        return HttpResponseRedirect('/page/%d/' % page_id)

def site_blocks(request, site_slug):
    var_dict = {}
    site = get_object_or_404(Site, slug=site_slug)
    var_dict['site'] = site
    var_dict['proxies'] = proxies = Proxy.objects.filter(site=site).order_by('language__code')   
    qs = Block.objects.filter(site=site).order_by('xpath')
    var_dict['block_count'] = block_count = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page = request.GET.get('page', 1)
    try:
        site_blocks = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = 1
        site_blocks = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.num_pages
        site_blocks = paginator.page(paginator.num_pages)
    var_dict['page_size'] = PAGE_SIZE
    var_dict['page'] = page = int(page)
    var_dict['offset'] = (page-1) * PAGE_SIZE
    var_dict['before'] = steps_before(page)
    var_dict['after'] = steps_after(page, paginator.num_pages)
    var_dict['site_blocks'] = site_blocks
    return render_to_response('blocks.html', var_dict, context_instance=RequestContext(request))

def site_translated_blocks(request, site_slug):
    var_dict = {}
    site = get_object_or_404(Site, slug=site_slug)
    var_dict['site'] = site
    var_dict['translated_blocks'] = blocks = TranslatedBlock.objects.filter(block__site=site)
    var_dict['translated_blocks_count'] = blocks.count()
    return render_to_response('translated_blocks.html', var_dict, context_instance=RequestContext(request))

def get_or_add_string(request, text, language, site=None, string_type=UNKNOWN, add=False, txu=None, reliability=1):
    if isinstance(language, str):
        language = Language.objects.get(code=language)
    is_model_instance = False
    if site:
        strings = String.objects.filter(text=text, language=language, site=site)
    else:
        strings = String.objects.filter(text=text, language=language)
    if strings:
        is_model_instance = True
        string = strings[0]
    else:
        if add:
            string = String(text=text, language=language, txu=txu, site=site, string_type=string_type, reliability=reliability, user=request.user)
            string.save()
            is_model_instance = True
        else:
            string = String(text=text, language=language, site=site)
    return is_model_instance, string

def block(request, block_id):
    """
    view block specified and allow moving back and forth among blocks of the same site filtered by:
    - : more than  days old if  is positive, less than if  is negative
    - target_languages: one or more translation language (a subset of the proxy languages)
    - translation_: as , but with reference to the translated blocks
    - state: translated (at least one language), untranslated (at least one language), all
    """
    first_block = None
    if int(block_id) == 0:
        site_slug = request.GET.get('site', '')
        filter = request.GET.get('filter', '')
        target_code =request.GET.get('lang', '')
        if site_slug and filter:
            site = get_object_or_404(Site, slug=site_slug)
            blocks = Block.objects.filter(site=site)
            if filter == 'no_translate':
                blocks = blocks.filter(no_translate=True)
            elif filter == 'already' and target_code:
                blocks = blocks.filter(language_id=target_code)
            elif filter == 'partially' and target_code:
                pass
            elif filter == 'translated' and target_code:
                pass
            elif filter == 'revised' and target_code:
                pass
            if blocks:
                first_block = block = blocks.order_by('id')[0]
    else:
        block = get_object_or_404(Block, pk=block_id)
    proxy_languages = [proxy.language for proxy in block.site.get_proxies()]
    proxy_codes = [l.code for l in proxy_languages]
    target_languages = [l for l in proxy_languages if not l == block.language]
    BlockSequencerForm.base_fields['translation_languages'].queryset = Language.objects.filter(code__in=proxy_codes)
    save_block = apply_filter = goto = create = modify = '' 
    post = request.POST
    if post:
        save_block = post.get('save_block', '')
        # apply_filter = post.get('apply_filter', '')
        if not (save_block or apply_filter):
            for key in post.keys():
                if key.startswith('goto-'):
                    goto = int(key.split('-')[1])
                    block = get_object_or_404(Block, pk=goto)
        apply_filter = not (save_block or goto)
        if save_block:
            form = BlockEditForm(post)
            if form.is_valid():
                data = form.cleaned_data
                language = data['language']
                no_translate = data['no_translate']
                block.language = language
                block.no_translate = no_translate
                block.save()
        elif (apply_filter or goto):
            form = BlockSequencerForm(post)
            if form.is_valid():
                data = form.cleaned_data
                webpage_id = data['webpage']
                block_age = '' # data['block_age']
                translation_state = int(data['translation_state'])
                translation_languages = data['translation_languages']
                translation_codes = [l.code for l in translation_languages]
                translation_age = '' #data['translation_age']
                source_text_filter = data['source_text_filter']
                list_pages = False # data['list_pages']
    if not post or save_block or create or modify:
        translation_state = None
        translation_codes = []
        if not post and first_block:
            if filter == 'no_translate':
                translation_state = INVARIANT
            elif filter == 'already':
                translation_state = ALREADY
                translation_codes = [target_code]
        sequencer_context = request.session.get('sequencer_context', {})
        if sequencer_context:
            webpage_id = sequencer_context.get('webpage', None)
            block_age = sequencer_context.get('block_age', '')
            translation_state = translation_state or sequencer_context.get('translation_state', TO_BE_TRANSLATED)
            translation_codes = translation_codes or sequencer_context.get('translation_codes', [])
            translation_age = sequencer_context.get('translation_age', '')
            source_text_filter = sequencer_context.get('source_text_filter', '')
            list_pages = sequencer_context.get('list_pages', False)
            request.session['sequencer_context'] = {}
        else:
            webpage_id = None
            block_age = ''
            translation_state = TO_BE_TRANSLATED
            translation_codes = [proxy.language.code for proxy in block.site.get_proxies()]
            translation_age = ''
            source_text_filter = ''
            list_pages = False
        webpage_id = request.GET.get('webpage', webpage_id)
        translation_languages = translation_codes and Language.objects.filter(code__in=translation_codes) or []
    sequencer_context = {}
    sequencer_context['webpage'] = webpage_id
    sequencer_context['block_age'] = block_age
    sequencer_context['translation_state'] = translation_state
    sequencer_context['translation_codes'] = translation_codes
    sequencer_context['translation_age'] = translation_age
    sequencer_context['source_text_filter'] = source_text_filter
    sequencer_context['list_pages'] = list_pages
    request.session['sequencer_context'] = sequencer_context
    var_dict = {}
    var_dict['page_block'] = block
    webpage = webpage_id and Webpage.objects.get(pk=webpage_id) or None
    previous, next = block.get_navigation(webpage=webpage, translation_state=translation_state, translation_codes=translation_codes, source_text_filter=source_text_filter)
    var_dict['previous'] = previous
    var_dict['next'] = next
    var_dict['site'] = site = block.site
    var_dict['language'] = block.language or site.language
    var_dict['target_languages'] = target_languages
    var_dict['pages'] = block.webpages.all()
    var_dict['list_pages'] = list_pages
    if save_block or goto:
        return HttpResponseRedirect('/block/%d/' % block.id)        
    var_dict['edit_form'] = BlockEditForm(initial={'language': block.language, 'no_translate': block.no_translate,})
    var_dict['sequencer_form'] = BlockSequencerForm(initial={'webpage': webpage_id, 'block_age': block_age, 'translation_state': translation_state, 'translation_languages': translation_languages, 'translation_age': translation_age, 'source_text_filter': source_text_filter, 'list_pages': list_pages, })
    return render_to_response('block.html', var_dict, context_instance=RequestContext(request))

# def block_translate(request, block_id):
def block_translate(request, block_id, target_code):
    block = get_object_or_404(Block, pk=block_id)
    proxy_languages = [proxy.language for proxy in block.site.get_proxies()]
    proxy_codes = [proxy.language_id for proxy in block.site.get_proxies()]
    source_language = block.get_language()
    target_language = get_object_or_404(Language, code=target_code)
    BlockSequencerForm.base_fields['translation_languages'].queryset = Language.objects.filter(code__in=proxy_codes)
    # BlockSequencerForm.base_fields['extract_strings'] = forms.BooleanField(required=False, label='Extract strings', )
    save_block = apply_filter = goto = extract = '' 
    create = modify = ''
    translated_blocks = TranslatedBlock.objects.filter(block=block, language=target_language).order_by('-modified')
    translated_block = translated_blocks.count() and translated_blocks[0] or None
    """
    segments = block.block_get_segments(None)
    """
    if translated_block:
        segments = translated_block.translated_block_get_segments(None)
    else:
        segments = block.block_get_segments(None)
    # segments = [segment.strip(' .,;:*+-=').lower() for segment in segments]
    # segments = [segment.strip(' .,;:*+-=') for segment in segments]
    segments = [segment.strip() for segment in segments]
    extract_strings = False
    post = request.POST
    if post:
        save_block = post.get('save_block', '')
        # apply_filter = post.get('apply_filter', '')
        segment = request.POST.get('segment', '')
        string = request.POST.get('string', '')
        extract = request.POST.get('extract', '')
        # if not (save_block or apply_filter):
        if not save_block:
            for key in post.keys():
                if key.startswith('goto-'):
                    goto = int(key.split('-')[1])
                    block = get_object_or_404(Block, pk=goto)
                elif key.startswith('create-'):
                    create = key.split('-')[1]
                elif key.startswith('modify-'):
                    modify = key.split('-')[1]
        apply_filter = not (save_block or segment or string or extract or goto or create or modify)
        if save_block:
            form = BlockEditForm(post)
            if form.is_valid():
                data = form.cleaned_data
                language = data['language']
                no_translate = data['no_translate']
                block.language = language
                block.no_translate = no_translate
                block.save()
        elif create:
            translated_block = TranslatedBlock(block=block, language=Language.objects.get(code=create), state=PARTIALLY, editor=request.user)
            translated_block.body = post.get('translation-%s' % create)
            # print 'create: ', create, translation.body
            translated_block.save()
            segments = translated_block.translated_block_get_segments(None)
            if not segments:
                translated_block.state=TRANSLATED
                translated_block.save()
        elif modify:
            translated_block = TranslatedBlock.objects.filter(block=block, language=Language.objects.get(code=modify)).order_by('-modified')[0]
            translated_block.body = post.get('translation-%s' % modify)
            # print 'modify: ', modify, translation.body
            translated_block.save()
            segments = translated_block.translated_block_get_segments(None)
            if not segments:
                translated_block.state=TRANSLATED
                translated_block.save()
        elif (apply_filter or goto):
            form = BlockSequencerForm(post)
            if form.is_valid():
                data = form.cleaned_data
                webpage_id = data['webpage']
                block_age = '' # data['block_age']
                translation_state = int(data['translation_state'])
                translation_languages = data['translation_languages']
                translation_codes = [l.code for l in translation_languages]
                translation_age = '' #data['translation_age']
                source_text_filter = data['source_text_filter']
                extract_strings = False # data['extract_strings']
        elif extract:
            for segment in segments:
                # is_model_instance, segment_string = get_or_add_string(segment, source_language, add=True)
                is_model_instance, segment_string = get_or_add_string(request, segment, source_language, site=block.site, string_type=SEGMENT, add=True)
        elif segment:
            # is_model_instance, segment_string = get_or_add_string(segment, source_language, add=True)
            is_model_instance, segment_string = get_or_add_string(request, segment, source_language, site=block.site, string_type=SEGMENT, add=True)
        elif string:
            # is_model_instance, segment_string = get_or_add_string(string, source_language, add=True)
            is_model_instance, segment_string = get_or_add_string(request, string, source_language, site=block.site, add=True)
            return HttpResponseRedirect('/string_translate/%d/%s/' % (segment_string.id, proxy_codes[0]))
    if (not post) or save_block or create or modify or extract or segment or string:
        sequencer_context = request.session.get('sequencer_context', {})
        if sequencer_context:
            webpage_id = sequencer_context.get('webpage', None)
            block_age = sequencer_context['block_age']
            translation_state = sequencer_context.get('translation_state', TO_BE_TRANSLATED)
            translation_codes = sequencer_context.get('translation_codes', [proxy.language.code for proxy in block.site.get_proxies()])
            translation_age = sequencer_context.get('translation_age', '')
            source_text_filter = sequencer_context.get('source_text_filter', '')
            extract_strings = sequencer_context.get('extract_strings', False)
            request.session['sequencer_context'] = {}
        else:
            webpage_id = ''
            block_age = ''
            translation_state = TO_BE_TRANSLATED
            translation_codes = [proxy.language.code for proxy in block.site.get_proxies()]
            translation_age = ''
            extract_strings = False
        webpage_id = request.GET.get('webpage', webpage_id)
        translation_languages = translation_codes and Language.objects.filter(code__in=translation_codes) or []
    sequencer_context = {}
    sequencer_context['webpage'] = webpage_id
    sequencer_context['block_age'] = block_age
    sequencer_context['translation_state'] = translation_state
    sequencer_context['translation_codes'] = translation_codes
    sequencer_context['translation_age'] = translation_age
    sequencer_context['source_text_filter'] = source_text_filter
    sequencer_context['extract_strings'] = extract_strings
    request.session['sequencer_context'] = sequencer_context
    source_segments = []
    source_strings = []
    source_translations = []
    site_invariants = text_to_list(proxy.site.invariant_words)
    for segment in segments:
        if not segment:
            continue
        if not non_invariant_words(segment.split(), site_invariants=site_invariants):
            continue
        # if source_language in proxy_languages:
        if source_language == target_language:
            continue
        is_model_instance, segment_string = get_or_add_string(request, segment, source_language, add=extract or extract_strings)
        print 'segment_string: ',  segment_string
        if is_model_instance:
            """ NON CANCELLARE
            like_strings = find_like_strings(segment_string, max_strings=5)
            """
            like_strings = []
            source_strings.append(like_strings)
            translations = String.objects.filter(txu=segment_string.txu, language_id=target_code)
            print 'translations: ', segment_string.txu, target_code, translations
            source_translations.append(translations)
        else:
            segment_string.id = 0
            source_strings.append([])
            source_translations.append([])
        source_segments.append(segment_string)
    source_segments = zip(source_segments, source_strings, source_translations)
    print 'source_segments: ',  source_segments
    """
    target_strings = []
    for segment_strings in source_strings:
        translated_strings = []
        for s in segment_strings:
            strings = String.objects.filter(language=source_language, text=s, txu__isnull=False).order_by('-reliability')
            if strings.count():
                string = strings[0]
                translations = String.objects.filter(txu=string.txu, language=target_language)
                for translation in translations:
                    text = translation.text
                    if not text in translated_strings:
                        translated_strings.append(text)
        target_strings.append(translated_strings)
    """
    var_dict = {}
    var_dict['page_block'] = block
    webpage = webpage_id and Webpage.objects.get(pk=webpage_id) or None
    previous, next = block.get_navigation(webpage=webpage, translation_state=translation_state, translation_codes=translation_codes, source_text_filter=source_text_filter)
    var_dict['previous'] = previous
    var_dict['next'] = next
    var_dict['site'] = site = block.site
    var_dict['language'] = block.language or site.language
    var_dict['target_language'] = target_language
    var_dict['target_code'] = target_code
    # var_dict['pages'] = block.webpages.all()
    if save_block or goto:
        return HttpResponseRedirect('/block/%d/translate/%s/' % (block.id, target_code) )       
    var_dict['edit_form'] = BlockEditForm(initial={'language': block.language, 'no_translate': block.no_translate,})
    var_dict['sequencer_form'] = BlockSequencerForm(initial={'webpage': webpage_id, 'block_age': block_age, 'translation_state': translation_state, 'translation_languages': translation_languages, 'translation_age': translation_age, 'source_text_filter': source_text_filter,})
    var_dict['source_segments'] = source_segments
    var_dict['translated_block'] = translated_block
    # var_dict['target_strings'] = target_strings
    return render_to_response('block_translate.html', var_dict, context_instance=RequestContext(request))

def propagate_block_translation(request, block, translated_block):
    similar_blocks = Block.objects.filter(site=block.site, checksum=block.checksum)
    for similar_block in similar_blocks:
        if not similar_block.body == block.body:
            continue
        translated_blocks = TranslatedBlock.objects.filter(block=similar_block).order_by('-modified')
        if translated_blocks:
            similar_block_translation = translated_blocks[0]
            similar_block_translation.body = translated_block.body
            similar_block_translation.editor = translated_block.editor
        else:
            similar_block_translation = translated_block
            similar_block_translation.pk = None
            similar_block_translation.block = similar_block
        similar_block_translation.save()

# srx_filepath = os.path.join(RESOURCES_ROOT, 'segment.srx')
srx_filepath = os.path.join(RESOURCES_ROOT, 'it', 'segment.srx')
srx_rules = srx_segmenter.parse(srx_filepath)
italian_rules = srx_rules['Italian']
segmenter = srx_segmenter.SrxSegmenter(italian_rules)
re_parentheses = re.compile(r'\(([^)]+)\)')

def block_pages(request, block_id):
    var_dict = {}
    var_dict['page_block'] = block = get_object_or_404(Block, pk=block_id)
    var_dict['site'] = site = block.site
    var_dict['proxies'] =  proxies = Proxy.objects.filter(site=site)
    qs = block.webpages.all()
    var_dict['page_count'] = page_count = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page = request.GET.get('page', 1)
    try:
        block_pages = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = 1
        block_pages = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.num_pages
        block_pages = paginator.page(paginator.num_pages)
    var_dict['page_size'] = PAGE_SIZE
    var_dict['page'] = page = int(page)
    var_dict['offset'] = (page-1) * PAGE_SIZE
    var_dict['before'] = steps_before(page)
    var_dict['after'] = steps_after(page, paginator.num_pages)
    return render_to_response('block_pages.html', var_dict, context_instance=RequestContext(request))

def string_view(request, string_id):
    if not request.user.is_superuser:
        return empty_page(request);
    print string_id
    var_dict = {}
    var_dict['string'] = string = get_object_or_404(String, pk=string_id)
    var_dict['string_type'] = STRING_TYPE_DICT[string.string_type]
    var_dict['source_language'] = source_language = string.language
    var_dict['other_languages'] = other_languages = Language.objects.exclude(code=source_language.code).order_by('code')

    StringSequencerForm.base_fields['translation_languages'].queryset = other_languages
    string_context = request.session.get('string_context', {})
    if string_context:
        string_types = string_context.get('string_types', [])
        project_site_id = string_context.get('project_site', None)
        translation_state = string_context.get('translation_state', TO_BE_TRANSLATED)
        translation_codes = string_context.get('translation_codes', [l.code for l in other_languages])
        translation_subjects = string_context.get('translation_subjects', [])
        order_by = string_context.get('order_by', TEXT_ASC)
        show_similar = string_context.get('show_similar', False)
    else:
        string_types = []
        project_site_id = string.site.id
        translation_state = TO_BE_TRANSLATED
        translation_codes = [l.code for l in other_languages]
        translation_subjects = []
        order_by = TEXT_ASC
        show_similar = False
    translation_languages = Language.objects.filter(code__in=translation_codes)
    project_site = project_site_id and Site.objects.get(pk=project_site_id) or None
    print 'project_site: ', project_site

    apply_filter = goto = '' 
    post = request.POST
    if post:
        apply_filter = post.get('apply_filter', '')
        if not (apply_filter):
            for key in post.keys():
                if key.startswith('goto-'):
                    goto = int(key.split('-')[1])
                    string = get_object_or_404(String, pk=goto)
        # if (apply_filter or goto):
        form = StringSequencerForm(post)
        if form.is_valid():
            data = form.cleaned_data
            print 'data: ', data
            string_types = data['string_types']
            project_site = data['project_site']
            project_site_id = project_site and project_site.id or ''
            translation_state = int(data['translation_state'])
            translation_languages = data['translation_languages']
            translation_codes = [l.code for l in translation_languages]
            order_by = int(data['order_by'])
            show_similar = data['show_similar']
        else:
            print 'error', form.errors
    print 'project_site: ', project_site
    string_context['string_types'] = string_types
    string_context['translation_state'] = translation_state
    string_context['translation_codes'] = translation_codes
    string_context['project_site'] = project_site_id
    # string_context['translation_subjects'] = translation_subjects
    string_context['order_by'] = order_by
    string_context['show_similar'] = show_similar
    request.session['string_context'] = string_context
    if goto:
        return HttpResponseRedirect('/string/%d/' % string.id)        
    # previous, next = string.get_navigation(string_types=string_types, translation_state=translation_state, translation_codes=translation_codes, order_by=order_by)
    n, first, last, previous, next = string.get_navigation(string_types=string_types, site=project_site, translation_state=translation_state, translation_codes=translation_codes, order_by=order_by)
    var_dict['n'] = n
    var_dict['first'] = first
    var_dict['previous'] = previous
    var_dict['next'] = next
    var_dict['last'] = last
    var_dict['translations'] = string.get_translations()
    var_dict['similar_strings'] = show_similar and find_like_strings(string, max_strings=10) or []
    var_dict['sequencer_form'] = StringSequencerForm(initial={'string_types': string_types, 'project_site': project_site, 'translation_state': translation_state, 'translation_languages': translation_languages, 'order_by': order_by, 'show_similar': show_similar})
    return render_to_response('string_view.html', var_dict, context_instance=RequestContext(request))

def string_edit(request, string_id=None, language_code='', proxy_slug=''):
    user = request.user
    if not user.is_superuser:
        return empty_page(request)
    var_dict = {}
    string = string_id and get_object_or_404(String, pk=string_id) or None
    proxy = proxy_slug and get_object_or_404(Proxy, slug=proxy_slug) or None
    post = request.POST
    print 'post: ', post
    if post:
        if post.get('cancel', ''):
            if string_id:
                return HttpResponseRedirect('/string/%s/' % string_id)
            elif proxy_slug:
                return HttpResponseRedirect('/proxy/%s/translations/' % proxy_slug)
        elif post.get('save', '') or post.get('continue', ''):
            if string:
                string_edit_form = StringEditForm(post, instance=string)
            else:
                string_edit_form = StringEditForm(post)
            if string_edit_form.is_valid():
                string = string_edit_form.save()
                if not string.user == user:
                    string.user = user
                    string.save()
                if post.get('save', ''):
                    return HttpResponseRedirect('/string/%d/' % string.id)
    else:
        if string:
            string_edit_form = StringEditForm(instance=string)
        else:
            string_type = SEGMENT
            if proxy_slug:
                proxy = get_object_or_404(Proxy, slug=proxy_slug)
                site = proxy.site
                language = site.language
            elif language_code:
                site = None
                language = get_object_or_404(Language, code=language_code)
            else:
                site = None
                language = None
            reliability = 5
            text = ''
            path = ''
            user = request.user           
            string_edit_form = StringEditForm(initial={'string_type': string_type, 'site': site, 'language': language, 'reliability': reliability, 'text': text, 'path': path, 'user': user })
    var_dict['string'] = string
    var_dict['proxy'] = proxy
    var_dict['translations'] = string and string.get_translations() or []
    var_dict['string_edit_form'] = string_edit_form
    return render_to_response('string_edit.html', var_dict, context_instance=RequestContext(request))

def string_translate(request, string_id, target_code):
    if not request.user.is_superuser:
        return empty_page(request);
    var_dict = {}
    var_dict['string'] = string = get_object_or_404(String, pk=string_id)
    var_dict['string_type'] = STRING_TYPE_DICT[string.string_type]
    var_dict['source_language'] = source_language = string.language
    var_dict['target_code'] = target_code
    var_dict['target_language'] = target_language = Language.objects.get(code=target_code)
    translation_codes = [target_code]
    translation_languages = Language.objects.filter(code=target_code)

    StringSequencerForm.base_fields['translation_languages'].queryset = translation_languages

    string_context = request.session.get('string_context', {})
    if string_context:
        string_types = string_context.get('string_types', [])
        project_site_id = string_context.get('project_site', None)
        translation_state = string_context.get('translation_state', TO_BE_TRANSLATED)
        translation_codes = string_context.get('translation_codes', [target_code])
        translation_services = string_context.get('translation_services', [])
        translation_subjects = string_context.get('translation_subjects', [])
        order_by = string_context.get('order_by', TEXT_ASC)
        show_similar = string_context.get('show_similar', False)
    else:
        string_types = []
        project_site_id = string.site.id
        translation_state = TO_BE_TRANSLATED
        translation_codes = [target_code]
        translation_services = []
        translation_subjects = []
        order_by = TEXT_ASC
        show_similar = False
    project_site = project_site_id and Site.objects.get(pk=project_site_id) or None

    translation_form = StringTranslationForm()
    translation_service_form = TranslationServiceForm()
    apply_filter = goto = save_translation = '' 
    post = request.POST
    if post:
        apply_filter = post.get('apply_filter', '')
        ask_service = post.get('ask_service', '')
        """
        save_translation = post.get('save_translation', '')
        if not (apply_filter or ask_service or save_translation):
        """
        if not (apply_filter or ask_service):
            for key in post.keys():
                if key.startswith('goto-'):
                    goto = int(key.split('-')[1])
                    string = get_object_or_404(String, pk=goto)
                elif key.startswith('save-'):
                    save_translation = key.split('-')[1]
        if ask_service:
            translation_service_form = TranslationServiceForm(request.POST)
            if translation_service_form.is_valid():
                data = translation_service_form.cleaned_data
                translation_services = data['translation_services']
                if str(MYMEMORY) in translation_services:
                    langpair = '%s|%s' % (source_language.code, target_code)
                    status, translatedText, external_translations = ask_mymemory(string.text, langpair)
                    var_dict['external_translations'] = external_translations
                    var_dict['translation_service'] = TRANSLATION_SERVICE_DICT[MYMEMORY]
            else:
                print 'error', translation_service_form.errors
            translation_form = StringTranslationForm()
        elif save_translation:
            translation_form = StringTranslationForm(request.POST)
            if translation_form.is_valid():
                data = translation_form.cleaned_data
                print data
                translation = data['translation']
                site = data['translation_site']
                translation_subjects = data['translation_subjects']
                same_txu = data['same_txu']
                txu = string.txu
                if txu and same_txu:
                    target_txu = string.txu
                else:
                    provider = site and site.name or ''
                    target_txu = Txu(provider=provider, user=request.user)
                    target_txu.save()
                # is_model_instance, target = get_or_add_string(request, translation, target_language, site=translation_site, string_type=string.string_type, add=True, txu=target_txu, reliability=5)
                is_model_instance, target = get_or_add_string(request, translation, target_language, site=project_site, string_type=string.string_type, add=True, txu=target_txu, reliability=5)
                if not txu or not same_txu:
                    string.txu = target_txu
                    string.reliability = 5
                    string.save()
                for subject in translation_subjects:
                    try:
                        txu_subject = TxuSubject.objects.get(txu=txu, subject=subject)
                    except:
                        txu_subject = TxuSubject(txu=target_txu, subject=subject)
                        txu_subject.save()
            else:
                print 'error', translation_form.errors
                return render_to_response('string_translate.html', {'translation_form': translation_form,}, context_instance=RequestContext(request))
            translation_service_form = TranslationServiceForm()
        else: # apply_filter
            form = StringSequencerForm(post)
            if form.is_valid():
                data = form.cleaned_data
                string_types = data['string_types']
                project_site = data['project_site']
                project_site_id = project_site and project_site.id or ''
                translation_state = int(data['translation_state'])
                translation_languages = data['translation_languages']
                translation_codes = [l.code for l in translation_languages]
                order_by = int(data['order_by'])
                show_similar = data['show_similar']
    string_context['project_site'] = project_site_id
    string_context['translation_state'] = translation_state
    string_context['translation_codes'] = translation_codes
    string_context['translation_subjects'] = translation_subjects
    string_context['order_by'] = order_by
    string_context['show_similar'] = show_similar
    request.session['string_context'] = string_context
    if goto:
        return HttpResponseRedirect('/string_translate/%d/%s/' % (string.id, target_code))
    # previous, next = string.get_navigation(translation_state=translation_state, translation_codes=translation_codes)
    n, first, last, previous, next = string.get_navigation(string_types=string_types, site=project_site, translation_state=translation_state, translation_codes=translation_codes, order_by=order_by)
    var_dict['n'] = n
    var_dict['first'] = first
    var_dict['previous'] = previous
    var_dict['next'] = next
    var_dict['last'] = last
    var_dict['similar_strings'] = show_similar and find_like_strings(string, translation_languages=[target_language], with_translations=True, max_strings=10) or []
    # var_dict['translations'] = string.get_translations(target_languages=[target_language])
    var_dict['translations'] = string.get_translations()
    # var_dict['sequencer_form'] = StringSequencerForm(initial={'translation_state': translation_state, 'translation_languages': translation_languages, })
    var_dict['sequencer_form'] = StringSequencerForm(initial={'string_types': string_types, 'project_site': project_site, 'translation_state': translation_state, 'translation_languages': translation_languages, 'order_by': order_by, 'show_similar': show_similar})
    # var_dict['translation_form'] = StringTranslationForm(initial={'translation_site': translation_site, 'translation_subjects': translation_subjects,})
    var_dict['translation_form'] = StringTranslationForm(initial={'translation_site': project_site, 'translation_subjects': translation_subjects,})
    var_dict['translation_service_form'] = translation_service_form
    return render_to_response('string_translate.html', var_dict, context_instance=RequestContext(request))

def raw_tokens(text, language_code):
    tokens = re.split(" |\'", text)
    raw_tokens = []
    for token in tokens:
        # token = token.strip(STRIPPED[language_code])
        token = token.strip(DEFAULT_STRIPPED)
        if not token:
            continue
        raw_tokens.append(token)
    return raw_tokens     

def filtered_tokens(text, language_code, tokens=[], truncate=False, min_chars=10):
    """
    tokenize a text according to the language and strips some delimiter chars
    drop short tokens; remove last char
    """
    if not tokens:
        tokens = raw_tokens(text, language_code)
    filtered_tokens = []
    for token in tokens:
        n_chars = len(token)
        if n_chars < min_chars:
            continue
        if token in EMPTY_WORDS[language_code]:
            continue
        filtered_tokens.append(token)
    return filtered_tokens

def find_like_strings(source_string, translation_languages=[], with_translations=False, min_chars=3, max_strings=10, min_score=0.4):
    """
    source_string is an object of type String
    we look for similar strings of the same language
    first we use fuzzy search (more_like_this)
    then we find strings containing some of the same tokens
    """
    min_chars_times_10 = min_chars*10
    language = source_string.language
    language_code = language.code
    hits = list(SearchQuerySet().more_like_this(source_string))
    if not hits:
        return []
    source_tokens = filtered_tokens(source_string.text, language_code, truncate=True, min_chars=min_chars)
    source_set = set(source_tokens)
    like_strings = []
    for hit in hits:
        if not hit.language_code == language_code:
            continue
        try: # the index could be not in sync
            string = String.objects.get(language=language, text=hit.text)
        except:
            continue
        if with_translations:
            translations = string.get_translations(target_languages=translation_languages)
            if not translations:
                continue
        text = string.text
        tokens = raw_tokens(text, language_code)
        l = len(tokens)
        tokens = filtered_tokens(text, language_code, tokens=tokens, truncate=True, min_chars=min_chars)
        l = float(len(source_tokens) + l + len(tokens))/3
        like_set = set(tokens)
        i = len(like_set.intersection(source_set))
        if not i:
            continue
        # core  formula
        similarity_score = float(i * sqrt(i)) / sqrt(l)
        # print similarity_score, text
        # add a small pseudo-random element to compensate for the bias in the results of more_like_this
        correction = float(len(text) % min_chars) / min_chars_times_10
        similarity_score += correction
        if similarity_score < min_score:
            continue
        if with_translations:
            like_strings.append([similarity_score, string, translations])
        else:
            like_strings.append([similarity_score, string])
    like_strings.sort(key=lambda x: x[0], reverse=True)
    return like_strings[:max_strings]

def proxy_string_translations(request, proxy_slug=None, state=None):
    """
    list translations from source language (code) to target language (code)
    """
    if not request.user.is_superuser:
        return empty_page(request);
    PAGE_SIZE = 100
    proxy = proxy_slug and Proxy.objects.get(slug=proxy_slug) or None

    tm_edit_context = request.session.get('tm_edit_context', {})
    translation_state = state or tm_edit_context.get('translation_state', 0)
    project_site_id = proxy and proxy.site.id or tm_edit_context.get('project_site', None)
    project_site = project_site_id and Site.objects.get(pk=project_site_id) or None
    source_language_code = project_site and project_site.language_id or tm_edit_context.get('source_language', None)
    source_language = source_language_code and Language.objects.get(code=source_language_code) or None
    target_language_code = proxy and proxy.language_id or tm_edit_context.get('target_language', None)
    target_language = target_language_code and Language.objects.get(code=target_language_code) or None
    source_text_filter = tm_edit_context.get('source_text_filter', '')
    target_text_filter = tm_edit_context.get('target_text_filter', '')
    show_other_targets = tm_edit_context.get('show_other_targets', False)
    if proxy:
        tm_edit_context['project_site'] = project_site_id
        tm_edit_context['source_language'] = source_language_code
        tm_edit_context['target_language'] = target_language_code
        request.session['tm_edit_context'] = tm_edit_context
    if request.method == 'POST':
        post = request.POST
        form = StringsTranslationsForm(post)
        if post.get('delete-segment', ''):
            selection = post.getlist('selection')
            print 'delete-segment', selection
            for string_id in selection:
                string = String.objects.get(pk=int(string_id))
                txu = string.txu
                if txu:
                    for string in String.objects.filter(txu=txu):
                        string.delete()
                    txu.delete()
                else:
                    string.delete()
        elif post.get('delete-translation', ''):
            selection = post.getlist('selection')
            print 'delete-translation', selection
            for string_id in selection:
                string = String.objects.get(pk=int(string_id))
                txu = string.txu
                if txu:
                    translations = String.objects.filter(txu=txu, language=target_language)
                    for string in translations:
                        string.delete()
        elif post.get('make-invariant', ''):
            selection = post.getlist('selection')
            print 'make-invariant', selection
            for string_id in selection:
                string = String.objects.get(pk=int(string_id))
                txu = string.txu
                string.txu = None
                string.invariant = True
                string.save()
                if txu:
                    for string in String.objects.filter(txu=txu):
                        string.delete()
                    txu.delete()
        elif post.get('toggle-invariant', ''):
            selection = post.getlist('selection')
            print 'toggle-invariant', selection
            for string_id in selection:
                string = String.objects.get(pk=int(string_id))
                if string.invariant:
                    string.invariant = False
                    string.save()
                    print 'True-> False'
                elif not string.txu:
                    string.invariant = True
                    string.save()
                    print 'False-> True'
        elif form.is_valid():
            data = form.cleaned_data
            tm_edit_context['translation_state'] = translation_state = int(data['translation_state'])
            project_site = data['project_site']
            tm_edit_context['project_site'] = project_site and project_site.id or None
            source_language = data['source_language']
            tm_edit_context['source_language'] = source_language and source_language.code or None
            target_language = data['target_language']
            tm_edit_context['target_language'] = target_language and target_language.code or None
            tm_edit_context['source_text_filter'] = source_text_filter = data['source_text_filter']
            tm_edit_context['target_text_filter'] = target_text_filter = data['target_text_filter']
            tm_edit_context['show_other_targets'] = show_other_targets = data['show_other_targets']
            request.session['tm_edit_context'] = tm_edit_context
    else:
        form = StringsTranslationsForm(initial={'project_site': project_site, 'translation_state': translation_state, 'source_language': source_language, 'target_language': target_language, 'source_text_filter': source_text_filter, 'target_text_filter': target_text_filter, 'show_other_targets': show_other_targets, })

    if translation_state == TRANSLATED:
        translated = True
    elif translation_state == TO_BE_TRANSLATED:
        translated = False
    else:
        translated = None

    var_dict = {}
    var_dict['proxy'] = proxy
    var_dict['site'] = project_site_id and Site.objects.get(pk=project_site_id) or None
    var_dict['state'] = translation_state
    var_dict['source_language'] = source_language
    var_dict['target_language'] = target_language
    var_dict['show_other_targets'] = show_other_targets

    if project_site and translation_state == INVARIANT:
        qs = String.objects.filter(site=project_site, invariant=True)
    else:
        qs = find_strings(source_languages=[source_language], target_languages=[target_language], site=project_site, translated=translated, order_by='')
    if source_text_filter:
        qs = qs.filter(text__icontains=source_text_filter)
    if target_text_filter:
        qs = qs.filter(txu__string__text__icontains=target_text_filter)
    qs = qs.order_by('text')
    string_count = qs.count()
    var_dict['string_count'] = string_count
    paginator = Paginator(qs, PAGE_SIZE)
    page = request.GET.get('page', 1)
    try:
        strings = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = 1
        strings = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.num_pages
        strings = paginator.page(paginator.num_pages)
    var_dict['page_size'] = PAGE_SIZE
    var_dict['page'] = page = int(page)
    var_dict['offset'] = (page-1) * PAGE_SIZE
    var_dict['before'] = steps_before(page)
    var_dict['after'] = steps_after(page, paginator.num_pages)
    var_dict['strings'] = strings
    var_dict['strings_translations_form'] = form
    return render_to_response('proxy_string_translations.html', var_dict, context_instance=RequestContext(request))

def add_translated_string(request):
    user = request.user
    user_id = user.id
    if request.is_ajax() and request.method == 'POST':
        form = request.POST
        source_id = int(form.get('source_id'))
        translated_id = int(form.get('translated_id'))
        txu_id = int(form.get('txu_id'))
        translation = form.get('translation')
        target_language = form.get('t_l')
        source_language = form.get('s_l')
        site_name = form.get('site_name')
        target_language = Language.objects.get(name=target_language)
        source_language = Language.objects.get(name=source_language)
        reliability = 5
        if (txu_id == 0):
            print 'txu non esiste'
            target_txu = Txu(provider=site_name, user=request.user)
            target_txu.save()
            target_txu_id = target_txu.id
            print target_txu_id
            string = String.objects.filter(pk=source_id).update(txu=target_txu.id)
            string_new = String(text=translation, language=target_language, txu=target_txu, site=None, reliability=reliability, invariant=False)
            string_new.save()
            translated_new_id = string_new.id
            print translated_new_id
            return JsonResponse({"data": "add-txt-string","txu_id": target_txu_id,"translated_id": translated_new_id,})
        else:
            string = String.objects.filter(pk=translated_id)
            if string:
                print 'txu esiste update stringa'
                string.update(text=translation)
                return JsonResponse({"data": "modify-string",})
            else:
                print 'txu esiste nuova stringa'
                string_new = String(txu_id=txu_id, language=target_language, site=None, text=translation, reliability=reliability, invariant=False)
                string_new.save()
                translated_new_id = string_new.id
                return JsonResponse({"data": "add-string","translated_id": translated_new_id,})
    return empty_page(request);

def delete_translated_string(request):
    if request.is_ajax() and request.method == 'GET':
        form = request.GET
        source_id = int(form.get('source_id'))
        translated_id = int(form.get('translated_id'))
        txu_id = int(form.get('txu_id'))
        print source_id
        return JsonResponse({"data": "delete-string",})
    return empty_page(request);
    
def list_strings(request, sources, state, targets=[]):
    """
    list strings in the source languages with translations in the target languages
    """
    if not request.user.is_superuser:
        return empty_page(request);
    post = request.POST
    if post and post.get('delete_strings', ''):
        string_ids = post.getlist('delete')
        if string_ids:
            strings = String.objects.filter(id__in=string_ids)
            for string in strings:
                string.delete()
    PAGE_SIZE = 100
    var_dict = {}
    var_dict['sources'] = sources
    var_dict['state'] = state
    var_dict['targets'] = targets
    source_languages = target_languages = []
    translated = None
    can_delete = False
    if sources:
        source_codes = sources.split('-')
        source_languages = Language.objects.filter(code__in=source_codes).order_by('code')
    if targets:
        target_codes = targets.split('-')
        target_languages = Language.objects.filter(code__in=target_codes).order_by('code')
    if state == 'translated':
        translated = True
    elif state == 'untranslated':
        translated = False
        can_delete = not targets and request.user.is_superuser
    else:
        translated = None
    var_dict['can_delete'] = can_delete
    var_dict['source_languages'] = source_languages
    var_dict['target_languages'] = target_languages
    var_dict['target_codes'] = [l.code for l in target_languages]
    qs = find_strings(source_languages=source_languages, target_languages=target_languages, translated=translated)
    var_dict['string_count'] = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page = request.GET.get('page', 1)
    try:
        strings = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page = 1
        strings = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page = paginator.num_pages
        strings = paginator.page(paginator.num_pages)
    var_dict['page_size'] = PAGE_SIZE
    var_dict['page'] = page = int(page)
    var_dict['offset'] = (page-1) * PAGE_SIZE
    var_dict['before'] = steps_before(page)
    var_dict['after'] = steps_after(page, paginator.num_pages)
    var_dict['strings'] = strings
    return render_to_response('list_strings.html', var_dict, context_instance=RequestContext(request))

# def find_strings(source_languages=[], target_languages=[], translated=None, site=None):
def find_strings(source_languages=[], target_languages=[], translated=None, site=None, order_by=None):
    if isinstance(source_languages, Language):
        source_languages = [source_languages]
    if isinstance(target_languages, Language):
        target_languages = [target_languages]
    source_codes = [l.code for l in source_languages]
    target_codes = [l.code for l in target_languages]
    qs = String.objects
    if site:
        qs = qs.filter(site=site)
    if source_languages:
        source_codes = [l.code for l in source_languages]
        qs = qs.filter(language_id__in=source_codes)
    if translated is None:
        if not source_languages:
            qs = qs.all()
    elif translated: # translated = True
        if target_languages:
            # qs = qs.filter(as_source__target_code__in=target_codes).distinct()
            qs = qs.filter(txu__string__language_id__in=target_codes).distinct()
        """
        else:
            qs = qs.filter(as_source__isnull=False)
        """
    else: # translated = False
        if target_languages:
            """
            qs = qs.exclude(txu__string__language_id__in=target_codes)
            """
            qs = qs.exclude(invariant=True)
            if 'en' in target_codes:
                qs = qs.filter(Q(txu__isnull=True) | Q(txu__en=False))
            if 'es' in target_codes:
                qs = qs.filter(Q(txu__isnull=True) | Q(txu__es=False))
            if 'fr' in target_codes:
                qs = qs.filter(Q(txu__isnull=True) | Q(txu__fr=False))
            if 'it' in target_codes:
                qs = qs.filter(Q(txu__isnull=True) | Q(txu__it=False))
        """
        else:
            qs = qs.filter(as_source__isnull=True)
        """
    # return qs.order_by('language', 'text')
    if order_by is None:
        qs = qs.order_by('language', 'text')
    elif order_by:
        qs = qs.order_by(order_by)
    return qs

def get_language(language_code):
    return Language.objects.get(code=language_code)

if USE_SCRAPY:

    from scrapy.spiders import Rule #, CrawlSpider
    from scrapy.linkextractors import LinkExtractor
    from scrapy.crawler import CrawlerProcess
    from spiders import WipSiteCrawlerScript, WipCrawlSpider

    def site_crawl(site_pk):
        crawler = WipSiteCrawlerScript()
        site = Site.objects.get(pk=site_pk)
        crawler.crawl(
          site.id,
          site.slug,
          site.name,
          site.get_allowed_domains(),
          site.get_start_urls(),
          site.get_deny()
          )
    
    def site_crawl_by_slug(request, site_slug):
        site = get_object_or_404(Site, slug=site_slug)
        notask = request.GET.get('notask', False)
        if notask:
            site_name = site.name
            allowed_domains = site.get_allowed_domains()
            start_urls = site.get_start_urls()
            deny = site.get_deny()
            rules = [Rule(LinkExtractor(deny=deny), callback='parse_item', follow=True),]
            spider_class = type(str(site_slug), (WipCrawlSpider,), {'site_id': site.id, 'name':site_name, 'allowed_domains':allowed_domains, 'start_urls':start_urls, 'rules': rules})
            spider = spider_class()
            process = CrawlerProcess()
            process.crawl(spider)
            process.start() # the script will block here until the crawling is finished
            process.stop()
        else:
            print 'site_crawl_by_slug : ', site_slug
            """
            crawl_site.apply_async(args=(site.id,))
            """
            t = crawl_site.delay(site.id)
            print 'task id: ', t
        # return home(request)
        return HttpResponseRedirect('/site/%s/' % site_slug)
    
    from celery.utils.log import get_task_logger
    from celery_apps import app
    
    @app.task()
    def crawl_site(site_pk):
        logger = get_task_logger(__name__)
        logger.info('Crawling site {0}'.format(site_pk))
        return site_crawl(site_pk)
    
    """
    @app.task(ignore_result=True)
    def my_task(request):
        print('executing my_task')
        logger = get_task_logger(__name__)
        logger.debug('executing my_task')
        var_dict = {}
        return render_to_response('homepage.html', var_dict, context_instance=RequestContext(request))
    """

if USE_NLTK:

    import nltk
    from wip.wip_nltk.corpora import NltkCorpus
    from wip.wip_nltk.taggers import NltkTagger
    from wip.wip_nltk.chunkers import NltkChunker
    from wip.wip_nltk.util import filter_unicode
    
    tagged_corpus_id = 'itwac'
    file_ids = ['ITWAC-1.xml']
    tagger_types = ['BigramTagger', 'UnigramTagger', 'AffixTagger', 'DefaultTagger',]
    # default_tag = 'NOUN'
    default_tag = None
    filename = 'tagger'
    
    def create_tagger(request, language='it', filename=''):
        corpus_loader = getattr(nltk.corpus, tagged_corpus_id)
        tagged_corpus = NltkCorpus(corpus_loader=corpus_loader, language=language)
        tagged_sents = tagged_corpus.corpus_loader.tagged_sents(fileids=file_ids, simplify_tags=True)
        tagger = NltkTagger(language=language, tagger_types=tagger_types, default_tag=default_tag, train_sents=tagged_sents)
        tagger.train()
        data = pickle.dumps(tagger.tagger)
        if not filename:
            filename = '.'.join(file_ids)
        ext = '.pickle'
        if not filename.endswith(ext):
            filename += ext
        if request.GET.get('auto', False):
            filepath = os.path.join(DATA_ROOT, filename)
            f = open(filepath, 'wb')
            f.write(data)
            return HttpResponseRedirect('/')
        else:
            content_type = 'application/octet-stream'
            response = HttpResponse(data, content_type=content_type)
            response['Content-Disposition'] = 'attachment; filename="%s"' % filename
            return response
    
    def extract_terms(text, language='it', tagger=None, chunker=None):
        if text.startswith(u'\ufeff'):
            text = text[1:]
        if not tagger:
            tagger = NltkTagger(language=language, tagger_input_file=os.path.join(DATA_ROOT, tagger_filename))
        tagged_tokens = tagger.tag(text=text)
        if not chunker:
            chunker = NltkChunker(language='it')
        noun_chunks = chunker.main_chunker(tagged_tokens, chunk_tag='NP')
        phrases = []
        for chunk in noun_chunks:
            """
            tag = chunk[0][1].split(u':')[0]
            if tag in [u'ART', u'ARTPRE', 'DET']:
                chunk = chunk[1:]
                tag = chunk[0][1].split(u':')[0]
                if tag in ['DET']:
                    chunk = chunk[1:]
            """
            # phrase = u' '.join([tagged_token[0] for tagged_token in chunk])
            phrase = ' '.join([tagged_token[0] for tagged_token in chunk])
            phrases.append(phrase)
        return phrases
    
    def page_scan(request, fetched_id, language='it'):
        string = request.GET.get('strings', False)
        tag = request.GET.get('tag', False)
        chunk = request.GET.get('chunk', False)
        ext = request.GET.get('ext', False)
        string = tag = chunk = True
        if tag or chunk or ext:
            tagger = NltkTagger(language=language, tagger_input_file=os.path.join(DATA_ROOT, tagger_filename))
        if chunk or ext:
            chunker = NltkChunker(language='it')
        var_dict = {} 
        var_dict['scan'] = fetched = get_object_or_404(PageVersion, pk=fetched_id)
        var_dict['page'] = page = fetched.webpage
        var_dict['site'] = site = page.site
        page = fetched.webpage
        site = page.site
        if page.encoding.count('html'):
            if request.GET.get('region', False):
                region = page.get_region()
                var_dict['text_xpath'] = region and region.root
                var_dict['page_text'] = region and region.full_text.replace("\n"," ") or ''
            if string:
                var_dict['strings'] = [s for s in strings_from_html(fetched.body)]
            if chunk or tag:
                strings = []
                tags = []
                chunks = []
                for string in strings_from_html(fetched.body):
                    string = string.replace(u"\u2018", "'").replace(u"\u2019", "'")
                    if string.count('window') and string.count('document'):
                        continue
                    if tag or chunk:
                        tagged_tokens = tagger.tag(text=string)
                        if tag:
                            tags.extend(tagged_tokens)
                    if chunk:
                        noun_chunks = chunker.main_chunker(tagged_tokens, chunk_tag='NP')
                        chunks.extend(noun_chunks)
                    if not (tag or chunk):
                        """
                        matches = []
                        if string.count('(') and string.count(')'):
                            matches = re_parentheses.findall(string)
                            if matches:
                                for match in matches:
                                    string = string.replace('(%s)' % match, '')
                        """
                        # strings.extend(segmenter.extract(string)[0])
                        strings.extend(segments_from_string(string, site, segmenter))
                        """
                        for match in matches:
                            strings.extend(segmenter.extract(match)[0])
                        """
                        if ext:
                            terms = extract_terms(string, language=language, tagger=tagger, chunker=chunker)
                            terms = ['- %s -' % term for term in terms]
                            strings.extend(terms)
                var_dict['tags'] = tags
                var_dict['chunks'] = chunks
        return render_to_response('page_scan.html', var_dict, context_instance=RequestContext(request))
