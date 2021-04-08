<?php // vim: set expandtab tabstop=4 shiftwidth=4:

/**
 * Borderlands 3 Pakfile Contents Lookup
 * Copyright (C) 2021 CJ Kucera
 * 
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *     * Redistributions of source code must retain the above copyright
 *       notice, this list of conditions and the following disclaimer.
 *     * Redistributions in binary form must reproduce the above copyright
 *       notice, this list of conditions and the following disclaimer in the
 *       documentation and/or other materials provided with the distribution.
 *     * Neither the name of the development team nor the
 *       names of its contributors may be used to endorse or promote products
 *       derived from this software without specific prior written permission.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
 * DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 * LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
 * ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

// See bl3pakfile.schema.sql for the MySQL/MariaDB schema for this, and
// list_contents.py in the parent directory for how to populate the DB.
require_once('dbinfo.php');

$errors = array();
$searched_name = null;
$search_results = array();

$dbh = new mysqli('p:' . $dbhost, $dbuser, $dbpass, $dbname);
if (mysqli_connect_errno())
{
    array_push($errors, 'DB Connect error');
}
else
{
    if (array_key_exists('name', $_REQUEST))
    {
        $searched_name = trim($_REQUEST['name']);
        $searched_name = str_replace(array(' ', "\n", "\r", "\t", "\0", "\x0B"), '', $searched_name);

        # Some regexes we'll use while converting to "real" paths
        $plugins_re = '|^(?P<firstpart>\w+)/Plugins/(?P<lastpart>.*)\s*$|';
        $content_re = '|^(?P<junk>.*/)?(?P<firstpart>\w+)/Content/(?P<lastpart>.*)\s*$|';

        # Get the IDs and full pathnames
        $stmt = $dbh->prepare("
            select distinct
                p.dirname patchname, p.released, p.description,
                f.filename pakname, f.mountpoint, f.ordernum,
                o.filename_full
            from
                o2f m,
                pakfile f,
                patch p,
                object o
            where
                o.filename_base=?
                and m.oid=o.oid
                and m.fid=f.fid
                and f.pid=p.pid
            order by
                released,
                ordernum,
                filename_full
            ");
        $stmt->bind_param('s', $searched_name);
        $stmt->execute();
        $result = $stmt->get_result();
        while ($row = $result->fetch_assoc())
        {
            # Here's where we'll figure out the "real" path based on the mountpoint + in-pak
            # path.  Fun times!  We're definitely doing some needless work here, but it's
            # not like there's likely to be more than a hadful of results per page -- a few
            # dozen at most.
            $mountpoint = $row['mountpoint'];

            # Massage the mountpoint a bit
            if (substr($mountpoint, 0, 9) == '../../../')
            {
                $mountpoint = substr($mountpoint, 9);
            }
            elseif ($mountpoint == '/')
            {
                # This only ever shows up in "empty" pakfiles, so we should never hit this.
                $mountpoint = '';
            }

            # Slap the mountpoint on the path
            $real_path = $mountpoint . $row['filename_full'];

            # If we're a "plugin" path, strip off the plugin bit
            $matches = array();
            if (preg_match($plugins_re, $real_path, $matches))
            {
                $real_path = $matches['lastpart'];
            }

            # Now if we're a "content" path, strip that off as well
            if (preg_match($content_re, $real_path, $matches))
            {
                $firstpart = $matches['firstpart'];
                $lastpart = $matches['lastpart'];
                # I have no idea how to programmatically determine these hardcoded
                # translations.  They appear to be the only ones needed, though, at
                # least for "regular" objects.
                if ($firstpart == 'OakGame')
                {
                    $firstpart = 'Game';
                }
                elseif ($firstpart == 'Wwise')
                {
                    $firstpart = 'WwiseEditor';
                }
                $real_path = '/' . $firstpart . '/' . $lastpart;
            }

            # Now add in our converted 'real' path and append the row to our results list
            $row['filename_real'] = $real_path;
            array_push($search_results, $row);
        }
        $stmt->close();

    }
}
$dbh->close();

include('../../inc/apoc.php');
$page->set_title('Borderlands 3 Pakfile Contents Lookup');
$page->add_css('pakfile.css', 1);
$page->add_js('pakfile.js', 1);
$page->add_changelog('March 31, 2021', 'Initial release (data current through Jan 21, 2021\'s patch)');
$page->add_changelog('April 8, 2021', 'Updated with DLC6 (Director\'s Cut) data');
$page->apoc_header();

if (count($errors) > 0)
{
    echo "<div class=\"bad\">\n";
    echo "<ul>\n";
    foreach ($errors as $error)
    {
        echo "<li>$error</li>\n";
    }
    echo "</ul>\n";
    echo "</div>\n";
}
?>

<p>
This page can be used to find which pakfiles contain which Borderlands 3 game objects
(or other files stored inside BL3's pakfiles).  It's intended as a tool for anyone
interested in <a href="https://github.com/BLCM/BLCMods/wiki/Accessing-Borderlands-3-Data">accessing
Borderlands 3 data</a> for modding purposes, but who doesn't want to unpack literally
everything.  Using this page you can find out the specific pakfile which has what you
want and unpack just that one.
</p>

<p>
To search, input <b>only</b> the last "name" in the object to the textbox.  For
instance, to find which pakfiles contain <tt>/Game/PatchDLC/Raid1/GameData/Loot/ItemPoolExpansions/CharacterItemPoolExpansions_Raid1</tt>,
you'd just put <tt>CharacterItemPoolExpansions_Raid1</tt> in the search box.
This page does not currently support any wildcards -- you must know the actual
name of the object you're trying to look up.
</p>

<p>
Enjoy!  And <a href="/contact.php">let me know</a> if you find any bugs or have
any feature suggestions, etc.
</p>

<form method="GET" action="index.php">
<input type="text" name="name" size="100" value="<?php
if ($searched_name != null and count($search_results) == 0)
{
    echo htmlentities($searched_name);
}
?>">
<input type="submit" value="Search!">
</form>

<?php

if ($searched_name != null)
{
    if (count($search_results) == 0)
    {
        echo "<p class=\"bad\">No results found!</p>\n";
    }
    else
    {
        echo '<div class="results_divider"></div>' . "\n";
        echo '<h2>Results for: <tt>' . htmlentities($searched_name) . "</tt></h2>\n";
        echo "<p>\n";
        echo "<em>Choose a display mode:</em>\n";
        echo '<input type="radio" id="real" name="display" value="real" onChange="show_real();" checked><label for="real">"Real" Object Paths</label>' . "\n";
        echo '<input type="radio" id="pak" name="display" value="pak" onChange="show_pak();"><label for="pak">Raw Extracted Paths</label>' . "\n";
        echo "</p>\n";

        echo "<blockquote>\n";

        $prev_patch = '';
        foreach ($search_results as $row)
        {
            if ($row['patchname'] != $prev_patch)
            {
                if ($prev_patch != '')
                {
                    echo "</div>\n";
                }
                $prev_pak = '';
                $prev_patch = $row['patchname'];
                echo '<h2 class="pakfile_header">Data from ' . htmlentities($row['released']) . ' (' . htmlentities($row['description']) . ")</h2>\n";
                echo '<div class="pakfile_results">' . "\n";
            }
            if ($row['pakname'] != $prev_pak)
            {
                if ($prev_pak != '')
                {
                    echo "</ul>\n";
                }
                $prev_pak = $row['pakname'];
                echo "<p>\n";
                echo '<strong>' . $row['pakname'] . "</strong>\n";
                echo '<span class="pakfile_pak_text"><br /><i>Mountpoint: <tt>' . $row['mountpoint'] . "</tt></i></span>\n";
                echo "</p>\n";
                echo "<ul class=\"compact\">\n";
            }
            echo '<li class="pakfile_pak"><tt>' . htmlentities($row['filename_full']) . "</tt></li>\n";
            echo '<li class="pakfile_real"><tt>' . htmlentities($row['filename_real']) . "</tt></li>\n";
        }

        if ($prev_pak != '')
        {
            echo "</ul>\n";
        }
        if ($prev_patch != '')
        {
            echo "</div>\n";
        }

        echo "</blockquote>\n";
    }
}

?>

<!--
Eh, not gonna bother with this for now...
<p>
If you want a copy of the database itself, feel free to grab it:
<tt><a href=""></a></tt>.  It's a MariaDB/MySQL
database dump, but should probably import practically anywhere.
</p>
-->

<? $page->apoc_footer(); ?>
