#!/usr/bin/perl
# Copyright Matthew Wall
#
# Convert the changelog to various formats, or create a changelog stub suitable
# for inclusion in debian or redhat packaging.  Username and email are
# required.  This script uses gpg to guess username and email, since packages
# must be signed by gpg credentials with the username and email in the package
# changelog.
#
# examples of usage:
#   mkchangelog.pl --ifile docs/changes.txt > dist/README.txt
#   mkchangelog.pl --action stub --format redhat --release-version 3.4-1
#   mkchangelog.pl --action stub --format debian --release-version 3.4-2
#
#
# input format:
#
# x.y[.z] [mm/dd/(yy|YYYY)]
#
# Added README file (#42)
#
#
# debian format: (intended for /usr/share/doc/weewx/changelog.Debian)
#
# package (x.y.z) unstable; urgency=low
# * Added README file (#42)
# -- Joe Packager <joe at gmail.com>  Sat, 06 Oct 2012 06:50:47 -0500
#
#
# rpm format (three permissible variants) (intended for %changelog in .spec):
#
# * Wed Jun 14 2003 Joe Packager <joe at gmail.com> - 1.0-2
# - Added README file (#42).
#
# * Wed Jun 14 2003 Joe Packager <joe at gmail.com> 1.0-2
# - Added README file (#42).
#
# * Wed Jun 14 2003 Joe Packager <joe at gmail.com>
# - 1.0-2
# - Added README file (#42).

## no critic (RegularExpressions)
## no critic (ProhibitPostfixControls)
## no critic (InputOutput::RequireCheckedSyscalls)
## no critic (ProhibitCascadingIfElse)
## no critic (ProhibitManyArgs)
## no critic (RequireBriefOpen)
## no critic (ProhibitReusedNames)
## no critic (ProhibitBacktickOperators)
## no critic (ValuesAndExpressions::ProhibitMagicNumbers)
## no critic (ProhibitPunctuationVars)

use POSIX;
use Time::Local;
use Text::Wrap;
use strict;
use warnings;

my $user = 'Mister Package';
my $email = 'user@example.com';
my $pkgname = 'weewx';
my $ifn = q();                    # input filename
my $release = q();                # release version
my $action = 'app';               # what to do, can be app or stub
my $fmt = '80col';                # format can be 80col, debian, or redhat
my $rc = 0;
my $MAXCOL = 75;
my %MONTHS = ('jan',1,'feb',2,'mar',3,'apr',4,'may',5,'jun',6,
              'jul',7,'aug',8,'sep',9,'oct',10,'nov',11,'dec',12,);

($user,$email) = guessuser($user,$email);

while ($ARGV[0]) {
    my $arg = shift;
    if ($arg eq '--ifile') {
        $ifn = shift;
    } elsif ($arg eq '--release-version') {
        $release = shift;
    } elsif ($arg eq '--user') {
        $user = shift;
    } elsif ($arg eq '--email') {
        $email = shift;
    } elsif ($arg eq '--action') {
        $action = shift;
        if ($action ne 'app' && $action ne 'stub') {
            print {*STDERR} "mkchangelog: unrecognized action $action\n";
            $rc = 1;
        }
    } elsif ($arg eq '--format') {
        $fmt = shift;
        if ($fmt ne 'debian' && $fmt ne 'redhat') {
            print {*STDERR} "mkchangelog: unrecognized format $fmt\n";
            $rc = 1;
        }
    }
}

if ($action eq 'stub' && $release eq q()) {
    print {*STDERR} "mkchangelog: warning! no version specified\n";
}
if ($action eq 'app' && $ifn eq q()) {
    print {*STDERR} "mkchangelog: no input file specified\n";
    $rc = 1;
}
if ($user eq q()) {
    print {*STDERR} "mkchangelog: no user specified\n";
    $rc = 1;
}
if ($email eq q()) {
    print {*STDERR} "mkchangelog: no email specified\n";
    $rc = 1;
}

exit $rc if $rc != 0;

if ($action eq 'stub') {
    $rc = dostub($fmt, $release, $pkgname, $user, $email);
} elsif ($action eq 'app') {
    $rc = doapp($ifn, $fmt, $release, $pkgname, $user, $email);
}

exit $rc;




# create a skeletal changelog entry in the specified format.
# output goes to stdout.
sub dostub {
    my ($fmt, $version, $pkgname, $user, $email) = @_;
    my $rc = 0;
    my $msg = 'new upstream release';

    if ($fmt eq 'debian') {
        my $tstr = strftime '%a, %d %b %Y %H:%M:%S %z', localtime time;
        print {*STDOUT} "$pkgname ($version) unstable; urgency=low\n";
        print {*STDOUT} "  * $msg\n";
        print {*STDOUT} " -- $user <$email>  $tstr\n";
    } elsif ($fmt eq 'redhat') {
        my $tstr = strftime '%a %b %d %Y', localtime time;
        print {*STDOUT} "* $tstr $user <$email> - $version\n";
        print {*STDOUT} "- $msg\n";
    } else {
        print {*STDERR} "mkchangelog: unrecognized format $fmt\n";
        $rc = 1;
    }

    return $rc;
}


# convert the application log to the specified format.
# output goes to stdout.
sub doapp {
    my ($ifn, $fmt, $release, $pkgname, $user, $email) = @_;
    my $rc = 0;

    if (open my $IFH, '<', $ifn) {
        my @paragraphs;
        my $cp = q();
        my $version = q();
        my $ts = 0;
        while(<$IFH>) {
            my $line = $_;
            if ($line =~ /^([0-9]+\.[0-9.X]+)/) {
                my $v = $1;
                if ($version ne q()) {
                    dumpsection($fmt, $pkgname, $version, $user, $email, $ts,
                                \@paragraphs);
                } else {
                    # if a release version was specified, check the first
                    # version number in the changelog and ensure that it
                    # matches the release version.
                    if ($release ne q() && $version ne $release) {
                        print {*STDERR} "mkchangelog: latest changelog entry ($1) does not match release ($release)\n";
#                        exit 1;
                        $v = $release;
                    }
                }
                @paragraphs = (); # ignore anything before first valid version
                $version = $v;
                $ts = time;
                if ($line =~ /(\d+)\/(\d+)\/(\d+)/) {
                    my($month,$day,$year) = ($1,$2,$3);
                    $ts = timelocal(0,0,0,$day,$month-1,$year);
                } elsif ($line =~ /(\d+) (\S+) (\d+)/) {
                    my($day,$mstr,$year) = ($1,$2,$3);
                    $mstr = lc $mstr;
                    my $month = $MONTHS{$mstr};
                    $ts = timelocal(0,0,0,$day,$month-1,$year);
                }
            } elsif ($line =~ /\S/) {
                $cp .= $line;
            } else {
                push @paragraphs, $cp;
                $cp = q();
            }
        }
        push @paragraphs, $cp if $cp ne q();
        dumpsection($fmt,$pkgname, $version, $user, $email, $ts, \@paragraphs);
    } else {
        print {*STDERR} "mkchangelog: cannot read $ifn: $!\n";
        $rc = 1;
    }

    return $rc;
}

# print out a block of paragraphs in the appropriate format
sub dumpsection {
    my ($fmt, $pkgname, $version, $user, $email, $ts, $pref) = @_;
    my @paragraphs = @{$pref};
    return if ($#paragraphs < 0);

    my $prefix = q();
    my $firstlinepfx = q();
    my $laterlinepfx = q();
    my $postfix = q();

    if ($fmt eq '80col') {
#        my $tstr = strftime '%m/%d/%y', localtime $ts;
        my $tstr = strftime '%d %b %Y', localtime $ts;
        $prefix = "$version ($tstr)\n";
        $firstlinepfx = "\n";
        $postfix = "\n";
    } elsif ($fmt eq 'debian') {
        my $tstr = strftime '%a, %d %b %Y %H:%M:%S %z', localtime $ts;
        $prefix = "$pkgname ($version) unstable; urgency=low\n\n";
        $firstlinepfx = q(  * );
        $laterlinepfx = q(    );
        $postfix = "\n -- $user <$email>  $tstr\n\n\n";
    } elsif ($fmt eq 'redhat') {
        # use redhat format number 3
        my $tstr = strftime '%a %b %d %Y', localtime $ts;
        $prefix = " * $tstr $user <$email>\n - $version\n";
        $firstlinepfx = q( - );
        $laterlinepfx = q(   );
        $postfix = "\n";
    }

    # lines that beging with two or more spaces will be considered fixed space
    # and will not be subjected to word wrap.  we do this by replacing spaces
    # in those lines with the ~ character then padding them with the !
    # character, then replacing both after word wrap has been applied.
    print $prefix;
    foreach my $p (@paragraphs) {
        # escape lines that begin with spaces to prevent them from wrapping
        my @lines;
        foreach my $line (split /\n/,$p) {
            if ($line =~ /^\s+/) {
                $line =~ s/\s/~/g;
                while(length($line) < $MAXCOL) { $line .= q(!); }
            }
            push @lines, $line;
        }
        # do the word wrap
        $p = Text::Wrap::fill(q(),q(),join q( ), @lines);
        # unescape the fixed spacing lines
        @lines = ();
        foreach my $line (split /\n/,$p) {
            if ($line =~ /~/) {
                $line =~ s/~/ /g;
                $line =~ s/!//g;
            }
            push @lines, $line;
        }
        # print out the result
        my $pfx = $firstlinepfx;
        foreach my $ln (@lines) {
            print {*STDOUT} "$pfx$ln\n";
            $pfx = $laterlinepfx;
        }
    }
    print $postfix;
    return;
}

# use gpg to guess the user,email pair of the person running this script.
# if there are multiple gpg identities, then use the last one.
# if gpg gives us nothing, fallback to USER and USER@hostname.
sub guessuser {
    my($fb_user,$fb_email) = @_;
    my($user) = q();
    my($email) = q();
    my $env_user = $ENV{USER};
    if ($env_user ne q()) {
        my @lines = `gpg --list-keys $env_user`;
        foreach my $line (@lines) {
            if ($line =~ /$env_user/) {
                if ($line =~ /uid\s+(.*) <([^>]+)/) {
		    $user = $1;
		    $email = $2;
		    # strip off any [xxx] prefix (introduced in gpg 2017-ish)
		    $user =~ s/\s*\[[^\]]+\]\s*//;
                }
            }
        }
        if ($user eq q()) {
            $user = $env_user;
            my $hn = `hostname`;
            chop $hn;
            $email = $user . q(@) . $hn;
        }
    }
    $user = $fb_user if $user eq q();
    $email = $fb_email if $email eq q();
    return ($user,$email);
}
