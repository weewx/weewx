# Extensions

A key feature of WeeWX is its ability to be extended by installing 3rd party
*extensions*. Extensions are a way to package one or more customizations so that
they can be installed and distributed as a functional group.

Customizations typically fall into one of these categories:

* driver
* skin
* search list extension
* service
* generator

Take a look at the [WeeWX wiki](https://github.com/weewx/weewx/wiki) for a
sampling of some of the extensions that are available.

## Guidelines

Now that you have made some customizations, you might want to share those
changes with other WeeWX users. Put your customizations into an extension to
make installation, removal, and distribution easier.

Here are a few guidelines for creating extensions:

* Extensions should not modify or depend on existing skins. An extension
  should include its own, standalone skin to illustrate any templates, search
  list extension, or generator features.

* Extensions should not modify the database schemas. If it requires
  data not found in the default databases, an extension should provide its own
  database and schema.

* Extensions that require some measure of configuration for them to work should
  not be enabled by default. Otherwise, they will crash the system on startup.

* Extensions should generally have their own stanza in `weewx.conf`. Be sure to
  list all possible options in it, albeit commented out. This way the user will
  know what is available.

* Although one extension might use another extension, take care to write the
  dependent extension so that it fails gracefully. For example, a skin might use
  data from the forecast extension, but what happens if the forecast extension is
  not installed? Make the skin display a message about "forecast not installed"
  but otherwise continue to function.

## Packaging an extension

The structure of an extension mirrors that of WeeWX itself. If the
customizations include a skin, the extension will have a `skins` directory. If
the customizations include python code, the extension will have a `bin/user`
directory.

Each extension should also include:

* `readme.txt` or `readme.md` - a summary of what the extension does, a list of
  pre-requisites (if any), and instructions for installing the extension
  manually

* `changelog` - an enumeration of changes in each release

* `install.py` - python code used by the WeeWX `ExtensionInstaller`. More details
  below.

For example, here is the structure of an extension called `basic`, which
installs a skin called `Basic`. You can find it in the `examples` subdirectory.

```
basic
├── changelog
├── install.py
├── readme.md
└── skins
    └── Basic
        ├── basic.css
        ├── current.inc
        ├── favicon.ico
        ├── hilo.inc
        ├── index.html.tmpl
        ├── lang
        │   ├── en.conf
        │   └── fr.conf
        └── skin.conf
```

Here is the structure of an extension called `xstats`, which implements a search
list extension, as well as a simple skin. You can also find it in the `examples`
subdirectory.

```
xstats
├── bin
│   └── user
│       └── xstats.py
├── changelog
├── install.py
├── readme.txt
└── skins
    └── xstats
        ├── index.html.tmpl
        └── skin.conf
```

To distribute an extension, simply create a compressed archive of the
extension directory.

For example, create the compressed archive for the `basic` skin
like this:

    tar cvfz basic.tar.gz basic

Once an extension has been packaged, it can be installed using `weectl`:

    weectl extension install EXTENSION-LOCATION

## Default values

Whenever possible, an extension should *just work*, with a minimum of input from
the user. At the same time, parameters for the most frequently requested options
should be easily accessible and easy to modify. For skins, this might mean
parameterizing strings into `[Labels]` for easier customization. Or it might
mean providing parameters in `[Extras]` to control skin behavior or to
parameterize links.

Some parameters *must* be specified, and no default value would be appropriate.
For example, an uploader may require a username and password, or a driver might
require a serial number or IP address. In these cases, use a default value in
the configuration that will obviously require modification. The *username* might
default to *REPLACE_ME*. Also be sure to add a log entry that indicates the
feature is disabled until the value has been specified.

## Writing an installer

The installer is a python script called `install.py` that must be included in
your extension. It is used to specify the various parts of the extension, where
they should be put, and how they might be customized. To illustrate, let's take
a look at the `install.py` script for the `basic` skin. Here it is:

```python
def loader():                                                                # 1
    return BasicInstaller()


# By creating the configuration dictionary from a StringIO, we can preserve any comments
                                                                             # 2
BASIC_CONFIG = """
[StdReport]

    [[BasicReport]]
        skin = Basic
        enable = True
        # Language to use:
        lang = en
        # Unit system to use:
        unit_system = US
        # Where to put the results:
        HTML_ROOT = basic
"""

basic_dict = configobj.ConfigObj(StringIO(BASIC_CONFIG))                     # 3


class BasicInstaller(ExtensionInstaller):                                    # 4
    def __init__(self):
        super(BasicInstaller, self).__init__(                                # 5
            version="0.5",
            name='basic',
            description='Very basic skin for WeeWX.',
            author="Matthew Wall",
            author_email="mwall@users.sourceforge.net",
            config=basic_dict,                                               # 6
            files=[                                                          # 7
                ('skins/Basic',
                 ['skins/Basic/basic.css',
                  'skins/Basic/current.inc',
                  'skins/Basic/favicon.ico',
                  'skins/Basic/hilo.inc',
                  'skins/Basic/index.html.tmpl',
                  'skins/Basic/skin.conf',
                  'skins/Basic/lang/en.conf',
                  'skins/Basic/lang/fr.conf',
                  ]),
            ]
        )

    def configure(self, engine):                                             # 8
        """Customized configuration that sets a language code"""
        my_skin_path = os.path.join(os.path.dirname(__file__), 'skins/Basic')
        code = engine.get_lang_code(my_skin_path, 'en')
        self['config']['StdReport']['BasicReport']['lang'] = code
        return True
```

Going through this script line by line:

1. Every installer must define a `loader()` function that returns an instance of
   the installer class.

2. While you could specify the configuration dictionary as a Python structure,
   here we prefer to do it by creating and parsing a `StringIO` object. This has
   the advantage of preserving any comments in the configuration file.

3. Parse the configuration dictionary from the `StringIO` object.

4. Every installer must include an installer class that is a subclass of
   `ExtensionInstaller`. Here our class is called `BasicInstaller`.

5. The initializer for the installer class must call the initializer for the
   superclass, then initialize itself. This is where the various parts of the
   extension are specified. 

6. On this line, we set the configuration dictionary for our extension. Whatever
   appears in this dictionary will override and augment the configuration file
   `weewx.conf`. In this example, in the `[StdReport]` stanza, a new
   `[[BasicReport]]` stanza will be created. If there is already a `[[BasicReport]]`
   stanza, perhaps because we are upgrading, it will be overwritten.

7. The `files` attribute of the installer class is a list of tuples that specify
   the files to be installed. The first element of the tuple is the destination
   directory, and the second element is a list of files to be installed in that
   directory. In this case, the destination directory is `skins/Basic`.

8. The `configure()` method is called by the extension installer to allow any
   custom configuration to be performed. In this case, we use it to ask the user
   which language s/he wants, then set a language code appropriately. If the custom
   configuration is successful, the function should return `True`, otherwise
   `False`.

### Passing arguments on to your installer

It is possible to pass on additional command line arguments to your installer.
To do this, declare a method `process_args(self,args)` in your installer class.
Any arguments not recognized by `weectl extension install` will be passed on to
it.

For example, let's modify the `Basic` skin example above so that if a `--lang`
option is specified on the command line when installing the extension, the user
is not asked which language to use.

```python
import argparse

class BasicInstaller(ExtensionInstaller):
    def __init__(self):
        super().__init__(
            version="0.5",
            # ... as before ...

    def process_args(self, args):
        parser = argparse.ArgumentParser()
        parser.add_argument('--lang')
        namespace = parser.parse_args(args)
        # Set the language code or NONE, if no code was specified.
        self.lang = namespace.lang

    def configure(self, engine):
        """Customized configuration that sets a language code"""
        # If no language was specified on the command line, ask the user
        if not self.lang:
            my_skin_path = os.path.join(os.path.dirname(__file__), 'skins/Basic')
            self.lang = engine.get_lang_code(my_skin_path, 'en')
        self['config']['StdReport']['BasicReport']['lang'] = self.lang
        return True
```
