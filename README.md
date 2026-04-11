# 🎂 Ann Wanjiku's Birthday Website

A beautiful, interactive birthday website with animations, music, and photo galleries to celebrate Ann Wanjiku's special day.

## ✨ Features

- **🎨 Beautiful Animations**: Smooth CSS animations and transitions throughout
- **🎵 Background Music**: Integrated music player with playlist
- **📸 Photo Galleries**: Interactive photo galleries with lightbox
- **📱 Progressive Web App**: Installable on mobile devices
- **🎭 Interactive Elements**: Clickable animations and effects
- **🖼️ Photo Management**: Upload, replace, and organize photos
- **📝 Guest Book**: Leave birthday wishes and messages
- **🎪 Memory Slides**: Beautiful photo slideshows
- **🎁 Gift Registry**: Track gifts and contributions

## 🚀 Quick Start

### Option 1: Easy Start (Recommended)
1. Double-click `START_SERVER.bat`
2. Open your browser to `http://127.0.0.1:8000`

### Option 2: Manual Start
```bash
python server.py
```

## 📸 Photo Management

Manage photos easily through the web interface:

### Access Photo Manager
- **Web Interface**: Visit `http://127.0.0.1:8000/photo-admin`
- **Quick Access**: Double-click `PHOTO_MANAGER.bat`

### Features
- ✅ **Upload new photos** with drag & drop
- ✅ **Replace existing photos** seamlessly
- ✅ **Delete unwanted photos** safely
- ✅ **Assign photos to locations** (hero, gallery, memory slides)
- ✅ **Automatic backups** before changes
- ✅ **File validation** (size, type, format)

### Supported Formats
- JPG, JPEG, PNG, GIF, WebP
- Maximum file size: 10MB

## 📱 Mobile Installation

The website can be installed as a mobile app:

1. Open the website on your phone's browser
2. Look for "Add to Home Screen" option
3. The app will work offline with cached content

## 🎨 Customization

### Content Management
- Edit birthday data in `birthday_data.json`
- Upload photos via the photo manager
- Customize messages and settings through the admin panel

### Visual Customization
- Modify styles in `style.css`
- Change colors, fonts, and animations
- Add new interactive elements

## 🛠️ Technical Details

### Backend
- **Python HTTP Server** with custom request handling
- **REST API** for data management
- **File upload** with validation and security
- **Automatic backups** for data protection

### Frontend
- **Vanilla HTML/CSS/JavaScript** (no frameworks)
- **Progressive Web App** features
- **Responsive design** for all devices
- **Smooth animations** and transitions

### File Structure
```
├── server.py              # Main server application
├── birthday_data.json     # Website content and settings
├── style.css             # All styling and animations
├── home.html             # Welcome page
├── gallery.html          # Photo gallery
├── wishes.html           # Guest wishes
├── memories.html         # Memory slides
├── admin.html            # Content management
├── photo-admin.html      # Photo management interface
├── assets/
│   ├── photos/           # Photo storage
│   └── music/            # Audio files
├── START_SERVER.bat      # Easy server start
├── PHOTO_MANAGER.bat     # Photo management access
└── PHOTO_MANAGEMENT_README.md  # Detailed photo docs
```

## 🔧 API Endpoints

### Photo Management
- `GET /api/photos` - List all photos
- `POST /api/photos/upload` - Upload new photo
- `POST /api/photos/replace` - Replace existing photo
- `DELETE /api/photos/{filename}` - Delete photo
- `GET /api/photos/assignments` - Get photo assignments
- `POST /api/photos/assignments` - Update assignments

### Content Management
- `GET /api/birthday` - Get birthday data
- `POST /api/birthday` - Update birthday data
- `POST /api/birthday/reset` - Reset to defaults
- `GET /api/birthday/history` - View change history

## 🎵 Music Integration

- Background music with play/pause controls
- Multiple tracks in playlist
- Automatic playback (can be disabled)
- Music files stored in `assets/music/`

## 📊 Data Management

- All content stored in JSON format
- Automatic history tracking
- Backup system for safety
- Version control for changes

## 🔒 Security Features

- File type validation for uploads
- Size limits on all uploads
- Automatic filename sanitization
- Backup system for data protection
- Input validation on all forms

## 🐛 Troubleshooting

### Server Won't Start
- Ensure Python 3.x is installed
- Check that port 8000 is available
- Try running as administrator

### Photos Not Loading
- Clear browser cache
- Check file permissions
- Verify photo formats (JPG, PNG, GIF, WebP)

### Mobile App Issues
- Clear browser data
- Reinstall the PWA
- Check network connection

## 📝 Development

### Adding New Features
1. Add API endpoints in `server.py`
2. Create HTML pages as needed
3. Add styling in `style.css`
4. Test on multiple devices

### Code Style
- Python: Follow PEP 8
- HTML/CSS: Semantic markup, clean CSS
- JavaScript: Vanilla JS, no frameworks

## 📄 License

This project is created for celebrating Ann Wanjiku's birthday. Feel free to use and modify for similar celebrations!

## 🎉 Happy Birthday Ann Wanjiku!

This website was created with love to celebrate your special day. May it be filled with joy, beautiful memories, and all the happiness you deserve! ✨💖🎂

---

**Created with ❤️ for Ann Wanjiku's Birthday Celebration**