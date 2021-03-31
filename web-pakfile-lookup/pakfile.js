
function pakfileVis(classname, visibility)
{
    var elements = document.getElementsByClassName(classname);
    for (var i=0; i < elements.length; i++)
    {
        elements[i].style.display = visibility;
    }
}

function show_real()
{
    pakfileVis('pakfile_pak', 'none');
    pakfileVis('pakfile_pak_text', 'none');
    pakfileVis('pakfile_real', 'list-item');
}

function show_pak()
{
    pakfileVis('pakfile_real', 'none');
    pakfileVis('pakfile_pak', 'list-item');
    pakfileVis('pakfile_pak_text', 'inline');
}

