function loadManifest()
{
  const manifestUrl = '/api/clients';
  const container = document.getElementById('client-container');

  console.info('Loading clients...');

  fetch(manifestUrl)
    .then(response => {
      if (!response.ok) {
        const errorText = document.createElement('b');
        errorText.textContent = 'Failed to load clients. Please contact an administrator!';
        container.appendChild(errorText);
        throw new Error(`Error: ${response.status}`);
      }
      return response.json();
    })
    .then(manifest => {
      // Create client div's for each entry in manifest
      manifest.forEach(client => {
          if (!client.supported)
            return;

          if (!client.recommended)
            return;
          
          const div = document.createElement('div');
          div.style.maxWidth = client.screenshots[0].width;
          div.style.maxHeight = client.screenshots[0].height;
          div.classList.add('client');

          if (client.known_bugs) {
            const bugs = document.createElement('div');
            bugs.classList.add('known-bugs');
            bugs.title = client.known_bugs;
            const icon = document.createElement('a');
            icon.classList.add("fa-solid");
            icon.classList.add('fa-triangle-exclamation');
            icon.style.color = '#c40900';
            bugs.appendChild(icon);
            div.appendChild(bugs);
          }

          const version = document.createElement('p');
          version.textContent = client.name;
          version.classList.add('version')
          const description = document.createElement('p');
          description.textContent = client.description;
          description.classList.add('description')

          const screenshot = document.createElement('img');
          screenshot.src = client.screenshots[0].src;

          const downloadLink = document.createElement('a');
          downloadLink.classList.add('download-link');
          downloadLink.setAttribute('target', '_blank');
          downloadLink.textContent = 'Download';
          downloadLink.href = client.downloads[0];

          div.appendChild(version);
          div.appendChild(description);
          div.appendChild(screenshot);
          div.appendChild(downloadLink);

          container.appendChild(div);
      });
    })
    .catch(error => {
      const errorText = document.createElement('b');
      errorText.textContent = 'Failed to load clients. Please contact an administrator!';
      container.appendChild(errorText);
      console.error('Error loading client manifest:', error);
    });
}

window.addEventListener('load', loadManifest);
