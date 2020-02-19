# Known behavior of various RESTful services

## Wunderground (checked 5-Mar-2019)
* If all is OK, it responds with a code of 200, and a response body of `success`.

* If either the station ID, or the password is bad, it responds with a code of 401, and a response body of `unauthorized`.

* If the GET statement is malformed (for example, the date is garbled), it responds
with a code of 400, and a response body of `bad request`.

## PWS (checked 6-Mar-2019)
* If all is OK, it responds with a code of 200 and a response body with the following:

   ```
   <html>
   <head>
    <title>PWS Weather Station Update</title>
   </head>
   <body>
   Data Logged and posted in METAR mirror.

   </body>
   </html>
   ```

* If a bad station ID is given, it responds with a code of 200, and a response body with the following:
   ```
   <html>
   <head>
       <title>PWS Weather Station Update</title>
   </head>
   <body>
   ERROR: Not a vailid Station ID
   ```

* If a valid station ID is given, but a bad password, it responds with a code of 200, and a
response body with the following:
   ```
   <html>
   <head>
       <title>PWS Weather Station Update</title>
   </head>
   <body>
   ERROR: Not a vailid Station ID/Password
   ```

* If the date is garbled, it responds with a code of 200, and a response body with the following:
   ```
   <html>
   <head>
       <title>PWS Weather Station Update</title>
   </head>
   <body>
   dateutc parameter is not in proper format: YYYY-MM-DD HH:ii:ss<br>
   Data parameters invalid, NOT logged.

   </body>
   </html>
   ```

## WOW (checked 6-Mar-2019)
* If all is OK, it responds with a code of 200, and an empty JSON response body:
   ```
   {}
   ```

* If a valid station ID is given, but a bad password, it responds with a code of 403, and a
response body with the following:
   ```
   You do not have permission to view this directory or page.
   ```

* If the GET is garbled (e.g., a bad date), it responds with code 400, and response body
with the following:
   ```
   Bad Request
   ```
   
* If a post is done too soon (or, has already been seen, or is out of date --- not sure), it responds with code 429 ("Too many requests"), and a response body with the
following
   ```
   The custom error module does not recognize this error.
   ```
   
## AWEKAS (checked 6-Mar-2019)
* If all is OK, it responds with a code of 200, and a response body with a simple `OK`.

* If a bad user ID or password is given, it responds with a code of 200, and a 
response body with the following:
```
Benutzer/Passwort Fehler
```

* If a post is done too soon, it responds with a code of 200, and a response body with 
the following:
```
too many requests - try again later 
```

## Windy (checked 19 April 2019)
* If all is OK, it responds with a code of 200, and a response body with a simple `SUCCESS`.

* If a bad API key is given, it responds with a code of 400, and a response body with
the following
```
Invalid API key
```

* If the JSON payload is garbled, it responds with a code of 500, and a response body with
the following
```
We are sorry, but something broke.
```