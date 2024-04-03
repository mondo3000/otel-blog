import sqlite3
import os
from flask import Flask, render_template, request, url_for, flash, redirect
from werkzeug.exceptions import abort
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

resource = Resource(attributes={
    "service.name": "otel-blog",
    "service.namespace": "otel-blog",
    "environment": "development",
    "team": "blog-managers",
    "version": "1.5"
})

trace.set_tracer_provider(TracerProvider(resource=resource))

#Exporters
otlp_exporter_endpoint=os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']
otlp_exporter = OTLPSpanExporter(endpoint=otlp_exporter_endpoint, insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

app = Flask(__name__)
app.config['SECRET_KEY']='0101010101abcdef'

FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("index") as index:
        conn = get_db_connection()
        posts = conn.execute('SELECT * FROM posts').fetchall()
        conn.close()
        index.set_attribute("appdynamics.bt.name", "index")
    return render_template('index.html', posts=posts)

def get_post(post_id):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get-blog-post") as get_blog_post:
        conn = get_db_connection()
        post = conn.execute('SELECT * FROM posts WHERE id = ?',
                            (post_id,)).fetchone()
        conn.close()
        if post is None:
            abort(404)
        get_blog_post.set_attribute("appdynamics.bt.name", "get-blog-post")
    return post

@app.route('/<int:post_id>')
def post(post_id):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("blog-post"):
        post = get_post(post_id)
    return render_template('post.html', post=post)

@app.route('/create', methods=('GET', 'POST'))
def create():
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("create-blog-post") as create_blog_post:
        if request.method == 'POST':
            title = request.form['title']
            content = request.form['content']

            if not title:
                flash('Title is required!')
            else:
                conn = get_db_connection()
                conn.execute('INSERT INTO posts (title, content) VALUES (?, ?)',
                            (title, content))
                conn.commit()
                conn.close()
                return redirect(url_for('index'))
        create_blog_post.set_attribute("appdynamics.bt.name", "create_blog_post")
    return render_template('create.html')

@app.route('/<int:id>/edit', methods=('GET', 'POST'))
def edit(id):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("edit-blog-post") as edit_blog_post:
        post = get_post(id)

        if request.method == 'POST':
            title = request.form['title']
            content = request.form['content']

            if not title:
                flash('Title is required!')
            else:
                conn = get_db_connection()
                conn.execute('UPDATE posts SET title = ?, content = ?'
                            ' WHERE id = ?',
                            (title, content, id))
                conn.commit()
                conn.close()
                return redirect(url_for('index'))
        edit_blog_post.set_attribute("appdynamics.bt.name", "edit_blog_post")
    return render_template('edit.html', post=post)

@app.route('/<int:id>/delete', methods=('POST',))
def delete(id):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("delete-blog-post") as delete_blog_post:
        post = get_post(id)
        conn = get_db_connection()
        conn.execute('DELETE FROM posts WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        flash('"{}" was successfully deleted!'.format(post['title']))
        delete_blog_post.set_attribute("appdynamics.bt.name", "delete-blog-post")
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(port=5000)