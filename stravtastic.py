
# coding: utf-8

# # Scraping Strava Activities with requests
# Praise be to this dude here: https://brennan.io/2016/03/02/logging-in-with-requests/ for detailing a login-process using requests and lxml

import requests, lxml.html, re, gpxpy.gpx, datetime, os
from math import radians, cos, sin, asin, sqrt

strava_email = os.getenv('STRAVA_EMAIL', '')
strava_password = os.getenv('STRAVA_PASSWORD', '')

payload_strava = {
        'email': strava_email,
        'password': strava_password,
    }


def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km

def smooth_gpx(gpx_data=None, time_thresh=7, dist_thresh=10):
    smooth_gpx = []
    for gpx_activity in gpx_data:
        gpx = gpxpy.parse(gpx_activity)
        new_gpx = gpxpy.gpx.GPX()
        new_gpx_track = gpxpy.gpx.GPXTrack()
        new_gpx_segment = gpxpy.gpx.GPXTrackSegment()

        points_01 = gpx.tracks[0].segments[0].points
        last_point = len(points_01) - 1

        for num, p in enumerate(points_01):
            if num > 0:
                dist = haversine(p.longitude, p.latitude, prev_p.longitude, prev_p.latitude)
                td_int = (p.time - prev_p.time).total_seconds()
                if (td_int >= time_thresh and dist * 1000 >= dist_thresh) or num == last_point:
                    new_gpx_segment.points.append(p)
                    prev_p = p
            else:
                prev_p = p
        new_gpx_track.segments.append(new_gpx_segment)
        new_gpx.tracks.append(new_gpx_track)
        smooth_gpx.append(new_gpx.to_xml())
    return smooth_gpx

def get_strava_session():
    # log in to strava ad returns session for further
    login_form_url = 'https://www.strava.com/login'
    s = requests.session()
    headers = {"Accept-Language": "de-DE,de;q=0.5"}
    login = s.get(login_form_url, headers=headers)
    login_html = lxml.html.fromstring(login.text)
    hidden_inputs = login_html.xpath(r'//form//input[@type="hidden"]')
    hidden_values = {x.name: x.value for x in hidden_inputs}
    payload_strava.update(hidden_values)      # stuff that hidden form bullshit right in there.
    return s

def get_strava_dashboard(s):
    login_url = 'https://www.strava.com/session'
    response = s.post(login_url, data=payload_strava)
    return lxml.html.fromstring(response.content)

def get_strava_activity_stats(page):
    link_path = page.xpath('//h3//a/@href')
    time_path = page.xpath('//div//div//time/@datetime')
    activity_urls = [a for a in link_path if 'activities' in a]
    time_readable = [s.replace('\n', '')  for s in page.xpath('//div[1]/div/div[2]/time/time/text()')]
    # stats = page.xpath('//div[@class="entry-container"]/div[@class="entry-body"]/ul[contains(@class, "inline-stats")]')
    # stats_readable = [' '.join(s.text_content().split('\n')[:2]) for s in stats]
    stats_km = page.xpath('//div[2]/div/div[2]/div/div/ul/li[1]/div/b/text()')
    stats_time = page.xpath('//div[2]/div/div[2]/div/div/ul/li[2]/div/b/text()')
    # stats_readable = zip(map(lambda x: '{} km'.format(x), stats_km), map(lambda x: '{} min/km'.format(x), stats_time))
    stats_readable = ['{} km, {} min/km'.format(a, b) for (a, b) in zip(stats_km, stats_time)]
    return list(zip(time_readable, stats_readable, activity_urls))

def activity_choice(latest_activities):
    activity_menu = dict(enumerate(latest_activities))
    for i, a in activity_menu.items():
        print(i, ' | '.join(a))
    choose = None
    while True:
        user_input = input('Enter numbers separated by spaces: ')
        if user_input == '':
            user_input = '0'
        elif user_input.lower()[0] =='q':
            print('Exiting')
            exit()
        try:
            return list(map(int, user_input.split(',')))
        except ValueError:
            try:
                return list(map(int, user_input.split(' ')))
            except ValueError:
                    print('Please use spaces or commas to delimit the choices.')

def get_activity_gpx(s, choose, latest_activities):
    output_gpx = []
    for c in choose:
        current_url = ''.join(['https://www.strava.com', latest_activities[c][2], '/export_gpx'])
        output_gpx.append(s.get(current_url).text)
    return output_gpx


print('1. Getting Strava session and logging in.')
with get_strava_session() as s:
    print('2. Requesting Strava dashboard of logged in user')
    page = get_strava_dashboard(s)

    print('3. Fetching stats on latest activities')
    latest_activities = get_strava_activity_stats(page)

    print('4. Select activities to download:')
    choose = activity_choice(latest_activities)

    print('5. Download activities')
    output_gpx = get_activity_gpx(s, choose, latest_activities)

# destroy session

print('6. Save Original files')
for i, orig_xml in enumerate(output_gpx):
    orig_filename = '{:02d}_{}_orig.gpx'.format(choose[i], re.sub('\s+', '-', latest_activities[i][0]))
    # new_filepath = join(SMOOTHDIR, new_filename)
    print('-', orig_filename)
    # print('\n\n')
    with open(orig_filename, 'w') as orig_gpx_file:
        orig_gpx_file.write(orig_xml)

print('7. Smooth out GPX data')
smooth_xml = smooth_gpx(gpx_data=output_gpx, time_thresh=7, dist_thresh=10)

print('8. Save to files in current directory:')
for i, new_xml in enumerate(smooth_xml):
    new_filename = '{:02d}_{}_smooth.gpx'.format(choose[i], re.sub('\s+', '-', latest_activities[i][0]))
    # new_filepath = join(SMOOTHDIR, new_filename)
    print('-', new_filename)
    # print('\n\n')
    with open(new_filename, 'w') as new_gpx_file:
        new_gpx_file.write(new_xml)

print('9. Done!')
