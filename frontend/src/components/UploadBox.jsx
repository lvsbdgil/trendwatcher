export default function UploadBox({ loading, onUseSample, onCsvUpload }) {
  return (
    <div className="upload-box">
      <button className="primary-button" disabled={loading} onClick={onUseSample}>
        Запустить демо-пример
      </button>

      <label className="secondary-button">
        Загрузить CSV
        <input
          type="file"
          accept=".csv,text/csv"
          disabled={loading}
          onChange={(event) => onCsvUpload(event.target.files?.[0])}
        />
      </label>
    </div>
  );
}
