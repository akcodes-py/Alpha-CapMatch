export default function OrgSwitcher({ org, onChange }) {
  return (
    <label className="org-switcher">
      Organization
      <select value={org} onChange={(e) => onChange(e.target.value)}>
        <option value="northwind">northwind</option>
        <option value="bluebird">bluebird</option>
      </select>
    </label>
  );
}
