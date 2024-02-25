# Hardware guide

## Core hardware

Drivers for these stations are included in the core WeeWX distribution.  Each
station type provides a different set of observations, at different sampling
rates. These are enumerated in a *Station data* table in the page for each
station.

<table>
  <tr>
    <td><a href="../acurite">AcuRite</a></td>
    <td><a href="../te923">TE923</a></td>
    <td><a href="../wmr100">WMR100</a></td>
    <td><a href="../ws1">WS1</a></td>
  </tr>
  <tr>
    <td><a href="../cc3000">CC3000</a></td>
    <td><a href="../ultimeter">Ultimeter</a></td>
    <td><a href="../wmr300">WMR300</a></td>
    <td><a href="../ws23xx">WS23xx</a></td>
  </tr>
  <tr>
    <td><a href="../fousb">FineOffset</a></td>
    <td><a href="../vantage">Vantage</a></td>
    <td><a href="../wmr9x8">WMR9x8</a></td>
    <td><a href="../ws28xx">WS28xx</a></td>
  </tr>
 </table>


## Driver status

The following table enumerates many of the weather stations that are known to
work with WeeWX. If your station is not in the table, check the pictures at the
<a href="https://weewx.com/hardware.html">supported hardware page</a> &mdash;
it could be a variation of one of the supported models. You can also check the
<a href="https://weewx.com/hwcmp.html">station comparison</a> table &mdash;
sometimes new models use the same communication protocols as older hardware.

The maturity column indicates the degree of confidence in the driver. For
stations marked <em>Tested</em>, the station is routinely tested as part of
the release process and should work as documented. For stations not marked
at all, they are "known to work" using the indicated driver, but are not
routinely tested. For stations marked <em>Experimental</em>, we are still
working on the driver. There can be problems.

<table>
  <caption>Weather hardware supported by WeeWX</caption>
  <tr class="first_row">
    <td>Vendor</td>
    <td>Model</td>
    <td>Hardware<br/>Interface</td>
    <td>Required<br/>Package</td>
    <td>Driver</td>
    <td>Maturity</td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="8">AcuRite</td>
    <td>01025</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>01035</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>01036</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>01525</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>02032</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>02064</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>06037</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>06039</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>AcuRite<sup><a href='#acurite'>12</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">Argent Data Systems</td>
    <td>WS1</td>
    <td>Serial</td>
    <td class="code">pyusb</td>
    <td>WS1<sup><a href='#ads'>9</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Aercus</td>
    <td>WS2083</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WS3083</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="5">Ambient Weather</td>
    <td>WS1090</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>WS2080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>WS2080A</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>WS2090</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WS2095</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Cresta</td>
    <td>WRX815</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>PWS720</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="3">DAZA</td>
    <td>DZ-WH1080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>DZ-WS3101</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>DZ-WS3104</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="3">Davis</td>
    <td>VantagePro2</td>
    <td>Serial or USB</td>
    <td class="code">pyserial</td>
    <td>Vantage<sup><a href='#vantage'>1</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>VantagePro2</td>
    <td>WeatherLink IP</td>
    <td class="code">&nbsp;</td>
    <td>Vantage<sup><a href='#vantage'>1</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>VantageVue</td>
    <td>Serial or USB</td>
    <td class="code">pyserial</td>
    <td>Vantage<sup><a href='#vantage'>1</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Elecsa</td>
    <td>6975</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>6976</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">Excelvan</td>
    <td>Excelvan</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="11">Fine Offset</td>
    <td>WH1080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH1081</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH1091</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH1090</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WS1080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WA2080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WA2081</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH2080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH2081</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH3080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH3081</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="3">Froggit</td>
    <td>WS8700</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH1080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WH3080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="1">General Tools</td>
    <td>WS831DL</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="6">Hideki</td>
    <td>DV928</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>TE821</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>TE827</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>TE831</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>TE838</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>TE923</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">Huger</td>
    <td>WM918</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>WMR9x8<sup><a href='#wmr9x8'>4</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">IROX</td>
    <td>Pro X</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="4">La Crosse</td>
    <td>C86234</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WS28xx<sup><a href='#ws28xx'>7</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>WS-1640</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WS-23XX</td>
    <td>Serial</td>
    <td class="code">fcntl/select</td>
    <td>WS23xx<sup><a href='#ws23xx'>6</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>WS-28XX</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WS28xx<sup><a href='#ws28xx'>7</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Maplin</td>
    <td>N96GY</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>N96FY</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="3">Meade</td>
    <td>TE923W</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>TE923W-M</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>TE924W</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">Mebus</td>
    <td>TE923</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">National Geographic</td>
    <td>265</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="12">Oregon Scientific</td>
    <td>WMR88</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WMR88A</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WMR100</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WMR100N</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>WMR180</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WMR180A</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WMRS200</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WMR300</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR300<sup><a href="#wmr300">3</a></sup></td>
    <td>Experimental</td>
  </tr>
  <tr>
    <td>WMR300A</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR300<sup><a href="#wmr300">3</a></sup></td>
    <td>Experimental</td>
  </tr>
  <tr>
    <td>WMR918</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>WMR9x8<sup><a href='#wmr9x8'>4</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WMR928N</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>WMR9x8<sup><a href='#wmr9x8'>4</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td>WMR968</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>WMR9x8<sup><a href='#wmr9x8'>4</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="4">PeetBros</td>
    <td>Ultimeter 100</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>Ultimeter<sup><a href='#peetbros'>10</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>Ultimeter 800</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>Ultimeter<sup><a href='#peetbros'>10</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>Ultimeter 2000</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>Ultimeter<sup><a href='#peetbros'>10</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>Ultimeter 2100</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>Ultimeter<sup><a href='#peetbros'>10</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">RainWise</td>
    <td>Mark III</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>CC3000<sup><a href='#rainwise'>11</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>CC3000</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>CC3000<sup><a href="#rainwise">11</a></sup></td>
    <td>Tested</td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Radio Shack</td>
    <td>63-256</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WMR100<sup><a href='#wmr100'>2</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>63-1016</td>
    <td>Serial</td>
    <td class="code">pyserial</td>
    <td>WMR9x8<sup><a href='#wmr9x8'>4</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Sinometer</td>
    <td>WS1080 / WS1081</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WS3100 / WS3101</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan='2'>TechnoLine</td>
    <td>WS-2300</td>
    <td>Serial</td>
    <td class="code">fcntl/select</td>
    <td>WS23xx<sup><a href='#ws23xx'>6</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WS-2350</td>
    <td>Serial</td>
    <td class="code">fcntl/select</td>
    <td>WS23xx<sup><a href='#ws23xx'>6</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan='5'>TFA</td>
    <td>Matrix</td>
    <td>Serial</td>
    <td class="code">fcntl/select</td>
    <td>WS23xx<sup><a href='#ws23xx'>6</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>Nexus</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>Opus</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WS28xx<sup><a href='#ws28xx'>7</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>Primus</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>WS28xx<sup><a href='#ws28xx'>7</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>Sinus</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">Tycon</td>
    <td>TP1080WC</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Watson</td>
    <td>W-8681</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>WX-2008</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight">Velleman</td>
    <td>WS3080</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>FineOffsetUSB<sup><a href='#fousb'>5</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td class="text_highlight" rowspan="2">Ventus</td>
    <td>W831</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
  <tr>
    <td>W928</td>
    <td>USB</td>
    <td class="code">pyusb</td>
    <td>TE923<sup><a href='#te923'>8</a></sup></td>
    <td></td>
  </tr>
</table>

<ol>

<li><a id="vantage">Davis &quot;Vantage&quot; series</a> of weather stations,
including the <a href="http://www.davisnet.com/weather/products/vantage-pro-professional-weather-stations.asp">VantagePro2</a>&trade;
and <a href="https://www.davisinstruments.com/pages/vantage-vue">VantageVue</a>&trade;,
using serial, USB, or WeatherLinkIP&trade; connections. Both the &quot;Rev
A&quot; (firmware dated before 22 April 2002) and &quot;Rev B&quot; versions are
supported.
</li>

<li>
<a id="wmr100">Oregon Scientific WMR-100 stations.</a> Tested on the
<a href="https://www.oregonscientificstore.com/c-77-wmr100.aspx">Oregon
  Scientific WMR100N</a>.
</li>

<li>
<a id="wmr300">Oregon Scientific WMR-300 stations.</a> Tested on the
<a href="http://www.oregonscientificstore.com/p-358-oregon-scientific-wmr300-ultra-precision-professional-weather-system.aspx">Oregon
  Scientific WMR300A</a>.
</li>

<li>
<a id="wmr9x8">Oregon Scientific WMR-9x8 stations.</a> Tested on the
<a href="http://www.oregonscientificstore.com/oregon_scientific/product.asp?itmky=659831">Oregon Scientific WMR968</a>.
</li>

<li>
<a id="fousb">Fine Offset 10xx, 20xx, and 30xx stations.</a>
Tested on the Ambient Weather WS2080.
</li>

<li>
<a id="ws23xx">La Crosse WS-23xx stations.</a> Tested on the
<a href="https://www.lacrossetechnology.com/products/ws-2317">La Crosse 2317</a>.
</li>

<li>
<a id="ws28xx">La Crosse WS-28xx stations.</a> Tested on the
<a href="https://www.lacrossetechnology.com/products/c86234">La Crosse C86234</a>.
</li>

<li>
<a id="te923">Hideki Professional Weather Stations.</a> Tested on the Meade
TE923.
</li>

<li>
<a id="ads">ADS WS1 Stations.</a> Tested on the
<a href="http://www.argentdata.com/catalog/product_info.php?products_id=135">WS1</a>.
</li>

<li>
<a id="peetbros">PeetBros Ultimeter Stations.</a> Tested on the
<a href="http://www.peetbros.com/">Ultimeter 2000</a>.
</li>

<li>
<a id="rainwise">RainWise Mark III Stations.</a> Tested on the
<a href="http://www.rainwise.com/">CC3000</a>
(firmware "Rainwise CC-3000 Version: 1.3 Build 022 Dec 02 2016").
</li>

<li>
<a id="acurite">AcuRite Weather Stations.</a> Tested on the 01036RX.
</li>
</ol>
