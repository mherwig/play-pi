from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from gmusicapi import Webclient
from play_pi.settings import GPLAY_USER, GPLAY_PASS
from play_pi.models import *

class Command(BaseCommand):
    help = 'Initializes the database with your Google Music library'

    def handle(self, *args, **options):
        if GPLAY_PASS == "" or GPLAY_USER == "":
            self.stdout.write('Credentials not set up. Please edit settings.py')
            return

        api = Webclient()
        if not api.login(GPLAY_USER,GPLAY_PASS):
            self.stdout.write('Incorrect credentials, login failed')
            return

        self.stdout.write('Connected to Google Music, downloading data...')
        library = api.get_all_songs()
        self.stdout.write('Data downloaded!')
        self.stdout.write('Clearing DB...')
        cursor = connection.cursor()
        # This can take a long time using ORM commands on the Pi, so lets Truncate
        cursor.execute('TRUNCATE TABLE "{0}"'.format(Track._meta.db_table))
        cursor.execute('TRUNCATE TABLE "{0}"'.format(Album._meta.db_table))
        cursor.execute('TRUNCATE TABLE "{0}"'.format(Artist._meta.db_table))
        cursor.execute('TRUNCATE TABLE "{0}"'.format(Playlist._meta.db_table))
        self.stdout.write('Parsing new data...')

        # Easier to keep track of who we've seen like this...
        artists = []
        albums = []

        for song in library:
            track = Track()

            if song['albumArtist'] not in artists:
                artist = Artist()
                artist.name = song['albumArtist']
                try:
                    artist.art_url = song['artistImageBaseUrl']
                except:
                    artist.art_url = ""
                artist.save()
                artists.append(song['albumArtist'])
                self.stdout.write('Added artist: '+song['albumArtist'])
            else:
                artist = Artist.objects.get(name=song['albumArtist'])
            track.artist = artist

            if song['album'] not in albums:
                album = Album()
                album.name = song['album']
                album.artist = artist
                try:
                    album.art_url = song['albumArtUrl']
                except:
                    album.art_url = ""
                album.save()
                albums.append(song['album'])
            else:
                album = Album.objects.get(name=song['album'])
            track.album = album

            track.name = song['title']
            track.stream_id = song['id']
            try:
                track.track_no = song['track']
            except:
                track.track_no = 0
            track.save()

        self.stdout.write('All tracks saved!')
        self.stdout.write('Getting Playlists...')
        playlists = api.get_all_playlist_ids(auto=False, user=True)
        self.stdout.write('Saving playlists...')
        for name in playlists['user']:
            for pid in playlists['user'][name]:
                p = Playlist()
                p.pid = pid
                p.name = name
                p.save()

        for playlist in Playlist.objects.all():
            self.stdout.write('Getting playlist contents for ' + playlist.name)
            songs = api.get_playlist_songs(playlist.pid)
            for song in songs:
                track = Track.objects.get(stream_id=song['id'])
                pc = PlaylistConnection()
                pc.playlist = playlist
                pc.track = track
                pc.save()

        self.stdout.write('Library saved!')
