# [StdConvert]

The `StdConvert` service acts as a filter for units, converting the unit
system coming off your hardware to a target output unit system. All downstream
services, including the archiving service, will then see this unit system.
Hence, your data will be stored in the database using whatever unit system
you specify here.

*Once chosen, the unit system in the database cannot be changed!*

WeeWX does not allow you to mix unit systems within the databases. You must
choose a unit system and then stick with it. This means that users coming from
wview (which uses US Customary) should not change the default setting. Having
said this, there is a way of reconfiguring the database to use another unit
system. See the section [*Changing the unit system in an existing
database*](../../custom/database.md#change-unit-system) in the
*Customization Guide*.

!!! note
    This service only affects the units used in the databases. In particular,
    it has nothing to do with what units are displayed in plots or files.
    Those units are specified in the skin configuration file, as described
    in the *Customization Guide*, under section
    [*Changing unit systems*](../../custom/custom-reports.md#changing-unit-systems).
    Because of this, unless you have a special purpose application, there is
    really no good reason to change from the default, which is `US`.

!!! Warning
    If, despite these precautions, you do decide to change the units of data
    stored in the database, be sure to read the sections `[StdCalibrate]` and
    `[StdQC]`, and change the units there as well!

#### target_unit

Set to either `US`, `METRICWX`, or `METRIC`. The difference between `METRICWX`
and `METRIC` is that the former uses `mm` instead of `cm` for rain, and `m/s`
instead of `km/hr` for wind speed. See the reference section
[*Units*](../units.md) for the exact differences beween each of these options.

Default is `US`.