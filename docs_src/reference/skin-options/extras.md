# [Extras]

This section is available to add any static tags you might want to use
in your templates.

As an example, the `skin.conf` file for the *Seasons* skin
includes three options:


| Skin option         | Template tag                |
|---------------------|-----------------------------|
| `radar_img`         | `$Extras.radar_img`         |
| `radar_url`         | `$Extras.radar_url`         |
| `googleAnalyticsId` | `$Extras.googleAnalyticsId` |

If you take a look at the template `radar.inc` you will see
examples of testing for these tags.

#### radar_img

Set to an URL to show a local radar image for your region.

#### radar_url

If the radar image is clicked, the browser will go to this URL. This is
usually used to show a more detailed, close-up, radar picture.

For me in Oregon, setting the two options to:

``` ini
[Extras]
    radar_img = http://radar.weather.gov/ridge/lite/N0R/RTX_loop.gif
    radar_url = http://radar.weather.gov/ridge/radar.php?product=NCR&rid=RTX&loop=yes
```

results in a nice image of a radar centered on Portland, Oregon. When
you click on it, it gives you a detailed, animated view. If you live in
the USA, take a look at the [NOAA radar website](http://radar.weather.gov/)
to find a nice one that will work for you. In other countries, you will have
to consult your local weather
service.

#### googleAnalyticsId

If you have a [Google Analytics ID](https://www.google.com/analytics/),
you can set it here. The Google Analytics Javascript code will then be
included, enabling analytics of your website usage. If commented out,
the code will not be included.

### Extending `[Extras]`

Other tags can be added in a similar manner, including subsections. For
example, say you have added a video camera, and you would like to add a
still image with a hyperlink to a page with the video. You want all of
these options to be neatly contained in a subsection.

``` ini
[Extras]
    [[video]]
        still = video_capture.jpg
        hyperlink = http://www.eatatjoes.com/video.html
      
```

Then in your template you could refer to these as:

``` html
<a href="$Extras.video.hyperlink">
    <img src="$Extras.video.still" alt="Video capture"/>
</a>
```
