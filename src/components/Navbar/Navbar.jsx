import './Navbar.css';

function Navbar() {
    return (
        <nav>
            <div className="logo">
                <img src="" alt="BiletFlow Logo" />
            </div>

            <div className="nav_content">
                <a data-key="nav_about_us">About Us</a>
                <a data-key="nav_roadmap">Organizations</a>
                <a data-key="nav_competitions">Users</a>
            </div>

            <div className="lang">
                <a href="#" className="lang_current">ENG</a>

                <div className="lang_options">
                    <a href="#" data-lang="kaz">KAZ</a>
                    <a href="#" data-lang="eng">ENG</a>
                    <a href="#" data-lang="rus">RUS</a>
                </div>
            </div>

            <button className="signin_btn">Sign In</button>
        </nav>
    );
}

export default Navbar;