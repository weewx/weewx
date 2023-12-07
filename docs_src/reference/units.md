# Units

WeeWX offers three different *unit systems*:

<table>
    <caption>The standard unit systems used within WeeWX</caption>
    <tr>
        <th>Name</th>
        <th>Encoded value</th>
        <th>Description</th>
    </tr>
    <tr>
        <td class="first_col code">US</td>
        <td>0x01</td>
        <td>U.S. Customary</td>
    </tr>
    <tr>
        <td class="first_col code">METRICWX</td>
        <td>0x11</td>
        <td>Metric, with rain related measurements in <span class="code">mm</span> and speeds in <span
            class="code">m/s</span>
        </td>
    </tr>
    <tr>
        <td class="first_col code">METRIC</td>
        <td>0x10</td>
        <td>Metric, with rain related measurements in <span class="code">cm</span> and speeds in <span
            class="code">km/hr</span>
        </td>
    </tr>
</table>

The table below lists all the unit groups, their members, which units
are options for the group, and what the defaults are for each standard
unit system.

<table>
    <caption>Unit groups, members and options</caption>
    <tbody class="code">
    <tr>
        <th>Group</th>
        <th>Members</th>
        <th>Unit options</th>
        <th><span class="code">US</span></th>
        <th><span class="code">METRICWX</span></th>
        <th><span class="code">METRIC</span></th>
    </tr>
    <tr>
        <td class="first_col">group_altitude</td>
        <td>altitude<br/> cloudbase
        </td>
        <td>foot <br/> meter
        </td>
        <td>foot</td>
        <td>meter</td>
        <td>meter</td>
    </tr>
    <tr>
        <td class="first_col">group_amp</td>
        <td></td>
        <td>amp</td>
        <td>amp</td>
        <td>amp</td>
        <td>amp</td>
    </tr>
    <tr>
        <td class="first_col">group_angle</td>
        <td></td>
        <td>degree_angle<br/>radian</td>
        <td>degree_angle</td>
        <td>degree_angle</td>
        <td>degree_angle</td>
    </tr>
    <tr>
        <td class="first_col">group_boolean</td>
        <td></td>
        <td>boolean</td>
        <td>boolean</td>
        <td>boolean</td>
        <td>boolean</td>
    </tr>
    <tr>
        <td class="first_col">group_concentration</td>
        <td>no2<br/>pm1_0<br/>pm2_5<br/>pm10_0</td>
        <td>microgram_per_meter_cubed</td>
        <td>microgram_per_meter_cubed</td>
        <td>microgram_per_meter_cubed</td>
        <td>microgram_per_meter_cubed</td>
    </tr>
    <tr>
        <td class="first_col">group_count</td>
        <td>leafWet1<br/>leafWet2<br/>lightning_disturber_count<br/>lightning_noise_count<br/>lightning_strike_count<br/></td>
        <td>count</td>
        <td>count</td>
        <td>count</td>
        <td>count</td>
    </tr>
    <tr>
        <td class="first_col">group_data</td>
        <td></td>
        <td>byte<br/> bit</td>
        <td>byte</td>
        <td>byte</td>
        <td>byte</td>
    </tr>
    <tr>
        <td class="first_col">group_db</td>
        <td>noise</td>
        <td>dB</td>
        <td>dB</td>
        <td>dB</td>
        <td>dB</td>
    </tr>
    <tr>
        <td class="first_col">group_deltatime</td>
        <td>daySunshineDur<br/>rainDur<br/>sunshineDurDoc</td>
        <td>second<br/> minute<br/>hour<br/>day<br/></td>
        <td>second</td>
        <td>second</td>
        <td>second</td>
    </tr>
    <tr>
        <td class="first_col">group_degree_day</td>
        <td>cooldeg<br/> heatdeg<br/> growdeg
        </td>
        <td>degree_F_day<br/> degree_C_day</td>
        <td>degree_F_day</td>
        <td>degree_C_day</td>
        <td>degree_C_day</td>
    </tr>
    <tr>
        <td class="first_col">group_direction</td>
        <td>gustdir <br/> vecdir <br/> windDir <br/> windGustDir</td>
        <td>degree_compass</td>
        <td>degree_compass</td>
        <td>degree_compass</td>
        <td>degree_compass</td>
    </tr>
    <tr>
        <td class="first_col">group_distance</td>
        <td>windrun<br/>lightning_distance</td>
        <td>mile<br/>km</td>
        <td>mile</td>
        <td>km</td>
        <td>km</td>
    </tr>
    <tr>
        <td class="first_col">group_energy</td>
        <td></td>
        <td>kilowatt_hour<br/>mega_joule<br/>watt_hour<br/>watt_second</td>
        <td>watt_hour</td>
        <td>watt_hour</td>
        <td>watt_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_energy2</td>
        <td></td>
        <td>kilowatt_hour<br/>watt_hour<br/>watt_second</td>
        <td>watt_second</td>
        <td>watt_second</td>
        <td>watt_second</td>
    </tr>
    <tr>
        <td class="first_col">group_fraction</td>
        <td>co<br/>co2<br/>nh3<br/>o3<br/>pb<br/>so2</td>
        <td>ppm</td>
        <td>ppm</td>
        <td>ppm</td>
        <td>ppm</td>
    </tr>
    <tr>
        <td class="first_col">group_frequency</td>
        <td></td>
        <td>hertz</td>
        <td>hertz</td>
        <td>hertz</td>
        <td>hertz</td>
    </tr>
    <tr>
        <td class="first_col">group_illuminance</td>
        <td>illuminance</td>
        <td>lux</td>
        <td>lux</td>
        <td>lux</td>
        <td>lux</td>
    </tr>
    <tr>
        <td class="first_col">group_interval</td>
        <td>interval</td>
        <td>minute</td>
        <td>minute</td>
        <td>minute</td>
        <td>minute</td>
    </tr>
    <tr>
        <td class="first_col">group_length</td>
        <td></td>
        <td>inch<br/> cm
        </td>
        <td>inch</td>
        <td>cm</td>
        <td>cm</td>
    </tr>
    <tr>
        <td class="first_col">group_moisture</td>
        <td>soilMoist1 <br/> soilMoist2 <br/> soilMoist3 <br/> soilMoist4
        </td>
        <td>centibar</td>
        <td>centibar</td>
        <td>centibar</td>
        <td>centibar</td>
    </tr>
    <tr>
        <td class="first_col">group_percent</td>
        <td>
            cloudcover<br/>extraHumid1 <br/> extraHumid2 <br/> inHumidity <br/> outHumidity <br/>pop<br/>
            rxCheckPercent<br/>snowMoisture
        </td>
        <td>percent</td>
        <td>percent</td>
        <td>percent</td>
        <td>percent</td>
    </tr>
    <tr>
        <td class="first_col">group_power</td>
        <td></td>
        <td>kilowatt<br/>watt</td>
        <td>watt</td>
        <td>watt</td>
        <td>watt</td>
    </tr>
    <tr>
        <td class="first_col">group_pressure</td>
        <td>
            barometer <br/> altimeter <br/> pressure
        </td>
        <td>
            inHg<br/>mbar<br/>hPa<br/>kPa
        </td>
        <td>inHg</td>
        <td>mbar</td>
        <td>mbar</td>
    </tr>
    <tr>
        <td class="first_col">group_pressurerate</td>
        <td>
            barometerRate <br/> altimeterRate <br/> pressureRate
        </td>
        <td>
            inHg_per_hour <br/> mbar_per_hour <br/> hPa_per_hour <br/> kPa_per_hour
        </td>
        <td>inHg_per_hour</td>
        <td>mbar_per_hour</td>
        <td>mbar_per_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_radiation</td>
        <td>maxSolarRad <br/> radiation</td>
        <td>watt_per_meter_squared</td>
        <td>watt_per_meter_squared</td>
        <td>watt_per_meter_squared</td>
        <td>watt_per_meter_squared</td>
    </tr>
    <tr>
        <td class="first_col">group_rain</td>
        <td>rain<br/>ET<br/>hail<br/>snowDepth<br/>snowRate</td>
        <td>inch <br/> cm <br/> mm
        </td>
        <td>inch</td>
        <td>mm</td>
        <td>cm</td>
    </tr>
    <tr>
        <td class="first_col">group_rainrate</td>
        <td>rainRate <br/> hailRate
        </td>
        <td>inch_per_hour <br/> cm_per_hour <br/> mm_per_hour
        </td>
        <td>inch_per_hour</td>
        <td>mm_per_hour</td>
        <td>cm_per_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_speed</td>
        <td>wind <br/> windGust <br/> windSpeed <br/> windgustvec <br/> windvec
        </td>
        <td>mile_per_hour <br/> km_per_hour <br/> knot <br/> meter_per_second <br/> beaufort
        </td>
        <td>mile_per_hour</td>
        <td>meter_per_second</td>
        <td>km_per_hour</td>
    </tr>
    <tr>
        <td class="first_col">group_speed2</td>
        <td>rms <br/> vecavg
        </td>
        <td>mile_per_hour2 <br/> km_per_hour2 <br/> knot2 <br/> meter_per_second2
        </td>
        <td>mile_per_hour2</td>
        <td>meter_per_second2</td>
        <td>km_per_hour2</td>
    </tr>
    <tr>
        <td class="first_col">group_temperature</td>
        <td>appTemp <br/> dewpoint <br/> extraTemp1 <br/> extraTemp2 <br/> extraTemp3 <br/> heatindex <br/>
            heatingTemp <br/> humidex <br/> inTemp <br/> leafTemp1 <br/> leafTemp2 <br/> outTemp <br/> soilTemp1
            <br/> soilTemp2 <br/> soilTemp3 <br/> soilTemp4 <br/> windchill <br/> THSW
        </td>
        <td>degree_C<br/> degree_F <br/> degree_E<br/> degree_K
        </td>
        <td>degree_F</td>
        <td>degree_C</td>
        <td>degree_C</td>
    </tr>
    <tr>
        <td class="first_col">group_time</td>
        <td>dateTime</td>
        <td>unix_epoch <br/> dublin_jd
        </td>
        <td>unix_epoch</td>
        <td>unix_epoch</td>
        <td>unix_epoch</td>
    </tr>
    <tr>
        <td class="first_col">group_uv</td>
        <td>UV</td>
        <td>uv_index</td>
        <td>uv_index</td>
        <td>uv_index</td>
        <td>uv_index</td>
    </tr>
    <tr>
        <td class="first_col">group_volt</td>
        <td>consBatteryVoltage <br/> heatingVoltage <br/> referenceVoltage <br/> supplyVoltage
        </td>
        <td>volt</td>
        <td>volt</td>
        <td>volt</td>
        <td>volt</td>
    </tr>
    <tr>
        <td class="first_col">group_volume</td>
        <td></td>
        <td>cubic_foot<br/> gallon<br/> liter
        </td>
        <td>gallon</td>
        <td>liter</td>
        <td>liter</td>
    </tr>
    <tr>
        <td class="first_col">group_NONE</td>
        <td>NONE</td>
        <td>NONE</td>
        <td>NONE</td>
        <td>NONE</td>
        <td>NONE</td>
    </tr>
    </tbody>
</table>
