# Adding new, derived types

In the section [*Adding a second data source*](#Adding_2nd_source), we
saw an example of how to create a new type for a new data source. But,
what if you just want to add a type that is a derivation of existing
types? The WeeWX type `dewpoint` is an example of this: it's a
function of two observables, `outTemp`, and `outHumidity`.
WeeWX calculates it automatically for you.

Calculating new, derived types is the job of the WeeWX XTypes system. It
can also allow you to add new aggregation types.

See the Wiki article [*WeeWX V4 user defined
types*](https://github.com/weewx/weewx/wiki/WeeWX-V4-user-defined-types)
for complete details on how the XTypes system works.
